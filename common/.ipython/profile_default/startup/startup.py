# Imports

from __future__ import division
from datetime import datetime, timedelta
from functools import partial
from os import chdir
from pprint import pprint
import logging
import sys
import warnings

warnings.filterwarnings("ignore")

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn.apionly as sns

# Settings

# Pandas
pd.set_option("display.max_rows", 999)
pd.set_option("display.width", 160)
pd.set_option("precision", 2)

# Plotting
plt.ion()
plt.rc('figure', figsize=(18, 9))
