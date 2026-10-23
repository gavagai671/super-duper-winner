import argparse
from argparse import RawTextHelpFormatter
import yaml
import logging

class Struct:

    def __init__(self, **entries):
        self.__dict__.update(entries)

default_help_text = """

Config File Format:

log: 
  logfile: ../logs/compression_calculator.log
  loglevel: info
  max_bytes: 268435456
  num_rollover_logs: 5

mongo_db:
  dsn: mongodb://localhost/calculatordb
  pool_size: 30
"""


class Logger():
    
    def __init__(self, log=logging.getLogger(), options=None):   
        if isinstance(options, dict):
            numeric_loglevel = options['loglevel'] if 'loglevel' in options else logging.ERROR
            logfile = options['logfile'] if 'logfile' in options else 'log.txt'
            maxBytes = options['maxlogsize'] if 'maxlogsize' in options else 0
            numBackups = options['log_num_files'] if'log_num_files' in options else 0
        else:
            numeric_loglevel = options.loglevel if hasattr(options, 'loglevel') else logging.ERROR
            logfile = options.logfile if hasattr(options, 'logfile') else 'log.txt'
            maxBytes = options.maxlogsize if hasattr(options, 'maxlogsize') else 0
            numBackups = options.log_num_files if hasattr(options, 'log_num_files') else 0

        self.logger = log
        self.logger.setLevel(numeric_loglevel.upper())

#
        self.logFileHandler = (logging.handlers.RotatingFileHandler(
            logfile, encoding='utf-8', maxBytes=maxBytes, backupCount=numBackups)
                               if maxBytes > 0 else logging.FileHandler(logfile, encoding='utf-8'))
        self.formatter = logging.Formatter(
            '%(asctime)s, %(name)s, %(levelno)s, %(message)s, %(filename)s, %(lineno)d, %(funcName)s, %(process)d, %(thread)d')
        self.logFileHandler.setFormatter(self.formatter)

        self.logger.addHandler(self.logFileHandler)

        self.logger.warning('Program Start - Logging Initialized')
 
class GenericConfig(object):

    # default implementation does nothing
    def add_arguments(self, parser):
        pass

    def process_arguments(self):
        pass

    def __init__(self, helptext=default_help_text, config_file_name=None, args=None, config=None):

        self.args = None
        self.debug = False
        parser = argparse.ArgumentParser(description=helptext, formatter_class=RawTextHelpFormatter)
        parser.add_argument('-c', '--config_file', required=config is None, help='Config file with all required settings')
        parser.add_argument('-x', '--debug', required=False, help="Run in debug mode", action='store_true')
        self.add_arguments(parser)
        if config_file_name:
            args = ["--config", config_file_name]
        self.args = parser.parse_args(args)

        self.debug = self.args.debug
        config_file_name = self.args.config_file
        
        if not config and config_file_name:
            try:
                with open(config_file_name, 'r') as f:
                    config = yaml.safe_load(f)
            except Exception as e:
                print("Can't run without config file - err = " + str(e))
                print("Can't find config file = " + self.args.config_file)
                parser.print_help()
                raise
            
        if not config:
            print("Can't run without yaml configuration")
            parser.print_help()
            raise
        self.log = config['log']
                
        self.config = config

        self.process_arguments()
