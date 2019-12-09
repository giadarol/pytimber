import os
import getpass
import logging

import numpy as np

import cmmnbuild_dep_manager

user_home= os.environ['HOME']
nxcals_home = os.path.join(user_home,'.nxcals')
keytab= os.path.join(nxcals_home,'keytab')
certs = os.path.join(nxcals_home,'nxcals_cacerts')
username=getpass.getuser()


class NXCals(object):
    @staticmethod
    def create_certs():
        print(f"Creating {certs}")
        import urllib.request
        url="https://cafiles.cern.ch/cafiles/certificates/CERN%20Grid%20Certification%20Authority.crt"
        urllib.request.urlretrieve(url,filename="tmpcert")
        cmd=f"keytool -import -alias cerngridcertificationauthority -file tmpcert -keystore nxcals_cacerts -storepass nxcals -noprompt"
        print(cmd)
        os.system(cmd)
        os.rename("nxcals_cacerts",certs)
        os.unlink("tmpcert")
    def create_keytab():
        if not os.path.isdir(nxcals_home):
            os.mkdir(nxcals_home)
        print(f"""Please use:
        ktutil

ktutil: add_entry -password -p {username}@CERN.CH -k 1 -e arcfour-hmac-md5
ktutil: wkt {keytab}
ktutil: exit
kdestroy && kinit -f -r 5d -kt {keytab} {username}
klist
        """)

    def __init__(self,user=username,keytab=keytab,certs=certs,loglevel=logging.WARNING):
        """
        Needs
           user: default user name
           keytab: default $HOME/.nxcals/keytab
           certs: default $HOME/.nxcals/nxcals_cacerts
        """

        # Configure logging
        logging.basicConfig()
        self._log = logging.getLogger(__name__)
        if loglevel is not None:
            self._log.setLevel(loglevel)

        # Setup keytab and certs
        if os.path.isfile(keytab):
            self._keytab=keytab
        else:
            try:
                NXCals.create_keytab()
            except Exception as ex:
                print(ex)
                raise ValueError(f"Keytab file {keytab} does not exists")
        if os.path.isfile(certs):
            self._certs=certs
        else:
            try:
                NXCals.create_certs()
            except Exception as ex:
                print(ex)
                raise ValueError(f"Certificate file {certs} does not exists")

        self._user=user

        # Start JVM and set basic hook
        import cmmnbuild_dep_manager
        self._mgr=cmmnbuild_dep_manager.Manager('pytimber', loglevel)
        self._jpype=self._mgr.start_jpype_jvm()
        self._org=self._jpype.JPackage('org')
        self._cern=self._jpype.JPackage('cern')
        self._java=self._jpype.java
        self._System=self._java.lang.System

        # spark config
        try:
           self.spark=self._get_spark()
        except self._jpype.JavaException as ex:
            print(ex.message())
            print(ex.stacktrace())
            raise ex

        # nxcals config
        self._builders=self._cern.nxcals.api.extraction.data.builders
        #self.builders.FluentQuery
        #self.builders.KeyValuesQuery
        #self.builders.QueryData
        #self.builders.VariableQuery

        self._ServiceClientFactory=self._cern.nxcals.api.extraction.metadata.ServiceClientFactory

        self._variableService=self._ServiceClientFactory.createVariableService()
        self._entityService=self._ServiceClientFactory.createEntityService()
        #self._systemService=self._ServiceClientFactory.createSystemService()

        self._Variables=self._cern.nxcals.api.extraction.metadata.queries.Variables

        # Java helpers
        self._SparkDataFrameConversions=self._org.pytimber.utils.SparkDataFrameConversions



    #@property
    #def DevicePropertyQuery(self):
    #    return self.builders.DevicePropertyQuery.builder(self.spark)

    #@property
    #def VariableQuery(self):
    #    return self.builders.VariableQuery.builder(self.spark)

    #@property
    #def KeyValuesQuery(self):
    #    return self.builders.KeyValuesQuery.builder(self.spark)

    def _get_spark(self):
        self._System.setProperty("spring.main.web-application-type", "none")
        self._System.setProperty("javax.net.ssl.trustStore", self._certs)
        self._System.setProperty("javax.net.ssl.trustStorePassword", "nxcals")
        self._System.setProperty("kerberos.keytab", self._keytab)
        self._System.setProperty("kerberos.principal", self._user)
        self._System.setProperty("service.url", "https://cs-ccr-nxcals6.cern.ch:19093,https://cs-ccr-nxcals7.cern.ch:19093,https://cs-ccr-nxcals8.cern.ch:19093")

        self._NxcalsSparkSession=self._org.pytimber.utils.NxcalsSparkSession
        self._NxcalsSparkSession.setVerboseLogging(False);
        return self._NxcalsSparkSession.sparkSession()

    def searchVariable(self,pattern,system="CMW"):
        pattern=pattern.replace('%','%25')
        query=self._Variables.suchThat().systemName().eq(system).and_().variableName().like(pattern)
        out=[ k.getVariableName() for k in self._variableService.findAll(query)]
        return sorted(out)

    @property
    def DataQuery(self):
        return self._builders.DataQuery.builder(self.spark)

    def getVariable(self,variable,t1,t2,system="CMW",output='data'):
        ds=self.DataQuery.byVariables().system(system)\
                .startTime(t1).endTime(t2).variable(variable).buildDataset()
        if output =='spark':
            return ds
        elif output == 'data':
            return self.processVariable(ds)

    def processVariable(self,ds):
            ts_type=ds.dtypes()[1]._2()
            val_type=ds.dtypes()[2]._2()
            data=ds.sort('nxcals_timestamp').select('nxcals_timestamp','nxcals_value').na().drop()
            ts=self._SparkDataFrameConversions.extractDoubleColumn(data,"nxcals_timestamp")
            if val_type == "FloatType" or val_type == "DoubleType":
                val=self._SparkDataFrameConversions.extractDoubleColumn(data,"nxcals_value")
            elif val_type == "LongType":
                val=self._SparkDataFrameConversions.extractLongColumn(data,"nxcals_value")
            else :
                val=self._SparkDataFrameConversions.extractColumn(data,"nxcals_value")
            return  np.array(ts[:]/1e9,dtype=float),np.array(val[:])


    def searchEntity(self,pattern):
        out=[]
        for k in self._entityService.findByKeyValuesLike(pattern):
            d=k.entityKeyValues
            try:
               data=(d['variable_name'],d['device'],d['property'])
            except (NameError,TypeError) as ex:
                print(ex)
                data=k
            out.append(data)
        return out

    def searchDevice(self,pattern):
        out=[]
        for k in self._entityService.findByKeyValuesLike(pattern):
            d=k.entityKeyValues
            if d['device'] is not None:
                out.append( (d['device'],d['property']) )
        return out


