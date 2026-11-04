'''
Created on Apr 28, 2018

@author: bdiller
'''
from utility.generic_config import GenericConfig, Logger
from pymongo import MongoClient as Client
from sympy import diff, symbols
from datetime import datetime, timezone
import json
import regex
import timeit
import pandas
import logging
import sys
from math import log
from decimal import Decimal, getcontext
import multiprocessing
import concurrent.futures
from queue import Queue, Empty
from threading import Event
import threading
import signal
import functools
import platform
import time
import csv
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


class CalculatorSettings(GenericConfig):

    #     def __init__(self):
    #         super().__init__(config_file_name="calculator.yaml")

    def add_arguments(self, parser):
        parser.add_argument('-f', '--filename', required=False, help="csv of math instructions")
        parser.add_argument('-sh', '--show_history', action='store_true', required=False, help="show history")
        parser.add_argument('-e', '--eval', required=False, help="run eval on string. Assume text operands are filepaths")
        parser.add_argument('-l', '--log_command_file', required=False, help="compute log using base and value specified in csv")
        parser.add_argument('-g', '--gauss_summation', type=int, required=False, help="Solve for n: c = n(n+1)/2")
        parser.add_argument('-t', '--tag', required=False, help="tag")
        parser.add_argument('-vt', '--validate_tagged_results', required=False, help="validate tagged results")
        parser.add_argument('-b', '--base', required=False, help="base")
        parser.add_argument('-n', '--name', required=False, help="base")






class Calculator(object):
    BIT_MASK = 0xffffffff

    def __init__(self, options):
        sys.set_int_max_str_digits(10000)
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
            
    def export_to_csv(self):
        filename = "../logs/perf_stats.csv"
        with open(filename, 'w') as csvfilewriter:
            writer = csv.DictWriter(csvfilewriter, fieldnames=["index", "nanoseconds", "iterations"])
            writer.writeheader()
            for i, doc in enumerate(self.mongo_db.computation.find({"filename": "data/start_here/100_digits_pi2/calculate_custom_condition_server.csv"}).sort([('_id', -1)])):
                row = {
                    "index": i + 1,
                    "nanoseconds": eval(doc.get("elapsed_nanoseconds", doc.get("elapsed_nanoseonds"))),
                    "iterations": eval(doc.get("elapsed_iterations"))
                    
                }
                writer.writerow(row)

    def compute_log(self):
        MAX_SIZE = 1000000 * 2

        filename = self.options.args.log_command_file
        run_date = datetime.utcnow()
        result = None
        df = pandas.read_csv(filename)
        for _, row in df.iterrows():
            base = options.args.base or str(row.get("base"))
            _, base = self.eval(base) if base != 'e' else (None, base)

            value = str(row.get("value"))
            _, computed_value = self.eval(value)
            if not computed_value:
                if len(value) > MAX_SIZE:
                    self.logger.warn(
                        "Truncating input string after {} digits, because processor cannot effectively support larger integer values".format(self.MAX_SIZE))
                computed_value = eval(value[:MAX_SIZE])
            if base == 'e':
                result = log(computed_value)
            else:
                result = log(computed_value, base)

        computation = {
            "filename": filename,
            "result": result,
            "run_date": run_date
        }
        self.mongo_db.computation.update_one({"filename": computation['filename']}, computation, upsert=True, multi=False)

        my_print(result)
        return result

  


    def process_csv(self):
        filename = self.options.args.filename
        num_of_io_threads = self.options.config.get("io_threads", 0)
        if num_of_io_threads > 0:
            self.queue = Queue(maxsize=100)
            self.start_event = Event()

        run_date = datetime.now(timezone.utc)
        df = pandas.read_csv(filename)
        #csv_reader = csv.DictReader(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, chunksize=1000)
        for _, row in df.iterrows():
            break



    def show_history(self, result):
        if result:
            if self.options.args.show_history:
                query = {"filename": self.options.args.filename}
                results = list(self.mongo_db.computation.find(query).sort('_id', 1))
                for r in results:
                    del r["run_date"]
                    del r['_id']  # r = { field:value for r in results for field, value in r.items() if field != "run_date"}

                self.logger.debug(json.dumps(results, indent=1))
            elif not self.exit_sig_hdlr.terminate:
                my_print(result)


    def process(self):

        result = None
        for arg, value in self.options.args.__dict__.items():
            if value and arg in commands:
                try:
                    result = commands[arg]()
                    if self.exit_sig_hdlr.terminate:
                        self.logger.warn('Exiting {}:{} - SIGTERM Received'.format(arg, value))
                    else:
                        self.logger.info("Completed running {}:{}".format(arg, value))
                except:
                    self.logger.exception("Failed to process {}".format(sys.argv))
                    self.exit_sig_hdlr.terminate = True
                break
        if result and self.options.args.filename:
            self.show_history(result)


if __name__ == '__main__':
    options = CalculatorSettings()
    o = Calculator(options)
    #o.export_to_csv()
    o.process()
