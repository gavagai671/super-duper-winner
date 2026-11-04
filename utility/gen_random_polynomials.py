'''
Created on Apr 28, 2018

@author: bdiller
'''
from utility.generic_config import GenericConfig, Logger
from pymongo import MongoClient as Client
from datetime import datetime, timezone
import json
import regex
import timeit
import pandas
import logging
import sys
from math import log
import signal

import functools
import platform
import time
import distro

max_value = None

class Timer(object):
    
    def __init__(self):
        if hasattr(time, "thread_time_ns"):
            self.timer = time.thread_time_ns
            self.precision = 1
            self.precision_text = "nanoseonds"
        else:
            self.timer = time.process_time
            if len(str(self.timer()).split('.')[1]) < 9:
                self.precision_text = "milliseconds"
                self.precision = 10**3
            else:
                self.precision_text = "nanoseconds"
                self.precision = 10**9
                
    def elapsed_time(self, elapsed_time):
        elapsed_seconds = self.timer() - elapsed_time
        if self.precision > 1:
            return int(elapsed_seconds * self.precision)
        return elapsed_seconds

timer = Timer()

class Struct:

    def __init__(self, **entries):
        self.__dict__.update(entries)


def timing_logit(func, log_info=True):
    @functools.wraps(func)
    def wrap(*args, **kwargs):
        logging.info("Measuring execution time using time.{}".format(timer.timer.__name__))
        startTime = timer.timer()
        ret_val = func(*args, **kwargs)
        elapsedTime = timer.timer() - startTime
        info = 'function "{}" finished in {} {}'.format(func.__name__, timer.elapsed_time(elapsedTime), timer.precision_text)
        if log_info:
            logging.info(info)
        else:
            logging.debug(info)
#        print(info)
        return ret_val
    return wrap


class ExitSignalHandler:

    def __init__(self):
        self.terminate = False
        logging.warning('SIGNAL HANDLER Installed')

    def __call__(self, signum, frame):
        """
        This will be called by the python signal module

        https://docs.python.org/3/library/signal.html#signal.signal
        """
        if not self.terminate:
            self.terminate = True


def my_print(result):
    if len(str(result)) < 1000:
        print(my_hex(result))
    else:
        print("Result to large to print. Check result in Robomongo")


def bytes_needed(n):
    if n == 0:
        return 1
    if type(n) == int:
        return int(log(n, 256)) + 1
    return None


def gen_bytes(target):
    value = 256 ** target
    if bytes_needed(value) > target:
        return target, 256 ** (target - 1)
    else:
        return target, value


def my_hex(n):
    s = n.hex() if isinstance(n, float) else n if isinstance(n, str) else hex(n)
    return s


class GenRandomPolynomialSettings(GenericConfig):

    #     def __init__(self):
    #         super().__init__(config_file_name="calculator.yaml")

    def add_arguments(self, parser):
        parser.add_argument('-f', '--filename', required=False, help="csv of math instructions")
        parser.add_argument('-c', '--chunksize', type=int, required=False, help="chunk size")
        parser.add_argument('-t', '--number_of_terms', type=int, required=False, help="number of terms")
        parser.add_argument('-d', '--degree', type=int, required=False, help="maximum degree of polynomial")
        parser.add_argument('-n', '--number_of_polynomials', type=int, required=False, help="number of polynomials to generate")
        
        
class GenRandomPolynomial(object):

    def __init__(self, options):
        self.options = options
        Logger(options=options.log)
        self.logger = logging.getLogger("calculator")
        self.is_debug = self.logger.isEnabledFor(logging.DEBUG)
        self.is_info = self.logger.isEnabledFor(logging.INFO)

        if options.args.debug:
            ch = logging.StreamHandler()
            ch.setLevel(self.logger.level)
            self.logger.addHandler(ch)
        mongo_db = options.config['mongo_db']
        try:
            client = Client(host=mongo_db['dsn'], max_pool_size=mongo_db['pool_size'])
        except:
            client = Client(host=mongo_db['dsn'], maxPoolSize=mongo_db['pool_size'])
        self.mongo_db = client.get_default_database()
        self.exit_sig_hdlr = ExitSignalHandler()
        os = distro.id()
        supported_signals = [signal.SIGTERM, signal.SIGINT, signal.SIGHUP,
                             signal.SIGQUIT] if os == "debian" else [signal.SIGTERM, signal.SIGINT]
        for sig in supported_signals:
            signal.signal(sig, self.exit_sig_hdlr)
            
    def process(self):
		pass


if __name__ == '__main__':
    options = GenRandomPolynomialSettings()
    o = GenRandomPolynomial(options)
    #o.export_to_csv()
    o.process()
