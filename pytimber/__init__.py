# -*- coding: utf-8 -*-

from .pytimber import LoggingDB
from .dataquery import (
    DataQuery,
    parsedate,
    dumpdate,
    flattenoverlap,
    set_xaxis_date,
    set_xaxis_utctime,
    set_xlim_date,
    get_xlim_date,
)
from .LHCBSRT import BSRT
from .LHCBWS import BWS

from . import timberdata

from .pagestore import PageStore

from .nxcals import NXCals


__version__ = "2.9.0"

__cmmnbuild_deps__ = [
    "accsoft-cals-extr-client",
    "accsoft-cals-extr-domain",
#    "lhc-commons-cals-utils",
    "pytimber-utils",
    "slf4j-log4j12",
    "slf4j-api",
    "log4j",
]

__all__ = [
    "LoggingDB",
    "DataQuery",
    "parsedate",
    "dumpdate",
    "flattenoverlap",
    "set_xaxis_date",
    "set_xaxis_utctime",
    "set_xlim_date",
    "get_xlim_date",
    "BSRT",
    "BWS",
    "timberdata",
    "PageStore",
]

# workaround for missing keyword
# see (https://github.com/jpype-project/jpype/issues/540) to be fixed in new version
import jpype
jpype._pykeywords.KEYWORDS.add('and')
