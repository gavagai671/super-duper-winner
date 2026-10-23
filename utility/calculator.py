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


def gen_bytes(target):
    value = 256 ** target
    if bytes_needed(value) > target:
        return target, 256 ** (target - 1)
    else:
        return target, value


def my_hex(n):
    s = n.hex() if isinstance(n, float) else n if isinstance(n, str) else hex(n)
    return s


def msb(val, b=4):
    # return val >> (val.bit_length() - (8 * b))
    return eval(hex(val)[0:b + 2])


def bytes_needed(n):
    if n == 0:
        return 1
    if type(n) == int:
        return int(log(n, 256)) + 1
    return None


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


class AbstractFormulaParser(object):
    def __init__(self, row):
        self.target = None
        self.current_iteration = 0
        self.result = 0
        self.k = 0
        self.start_time = None
        self.start_iteration = 0
        self.log_interval = options.config.get("log_interval", 10**4)

    def compute(self, iteration):
        if self.increment and self.k and (iteration + 1) % self.k == 0:
            self.base += self.increment
            self.has_base_incremented = True
            
    def should_log(self):
        return ((self.current_iteration // (self.k or 1)) % self.log_interval) == 0

    def measure_elapsed_time(self):
        if self.should_log():
            elapsed_time = timer.timer() - self.start_time
            elapsed_iterations = self.current_iteration - self.start_iteration
            self.start_time = timer.timer()
            self.start_iteration = self.current_iteration
            return timer.elapsed_time(elapsed_time), elapsed_iterations
        return None, None


class FormulaParser(AbstractFormulaParser):

    def __init__(self, row):
        super().__init__(row)
        self.base = int(row['base'])
        self.exponents = [int(value) for col, value in row.items() if col.startswith("exponent") and value]
        self.constant = int(row.get("constant", 0))

    def compute(self, iteration):
        super().compute(iteration=iteration)
        for exp in self.exponents:
            r = pow(self.base, exp) + self.constant
        x = symbols('x')
        intermediate = x
        for exp in self.exponents:
            #intermediate = "pow({},{})".format(intermediate, exp)
            intermediate = "({}**{})".format(intermediate, exp)
        first_deriv = diff(eval(intermediate))
        second_deriv = diff(eval(intermediate), x, x)
        return r, first_deriv, second_deriv, intermediate if not self.constant else "{} + {}".format(intermediate, self.constant)


class FormulaFactory():
    @classmethod
    def make_formula(self, main_prog, row):
        if row.get("start"):
            return FormulaCustom(main_prog, row)
        if row.get("raise exponent"):
            return FormulaRaiseExponent(main_prog, row)
        if row.get("target_size"):
            return FormulaStopUntilTargetSize(main_prog, row)
        if row.get("k") and row.get("increment"):
            return FormulaIncBaseAfterKiteraions(main_prog, row)
        if row.get("target") or row.get("iterations"):
            return FormulaParserUnstructured(main_prog, row)

        raise Exception("Could not interpret csv file")


class FormulaParserUnstructured(AbstractFormulaParser):

    def __iter__(self):
        return self

    def _parse_exponent(self):
        self.base_formula = self.formula
        self.base_regex = regex.compile(r"^(((\(\s*))*)([0-9_a-z|\./]+)")
        self.exp_regex = regex.compile(r".*?\*\*\s*([0-9\.]+)")
        match = self.base_regex.match(self.formula)
        if match:
            try:
                s = match.group(4)
                self.base = eval(s)
            except:
                self.base = self.main_prog.get_computed_result(s)
                self.formula = self.formula.replace(s, str(self.base))
                self.base_formula = self.formula
            self.has_prefix = match.group(1) is not None
        else:
            raise Exception("Could not find base in {}".format(self.formula))
        match = self.exp_regex.match(self.formula)
        if match:
            self.exponent = eval(match.group(1))
        else:
            raise Exception("Could not find exponent in {}".format(self.formula))

    def __init__(self, main_prog, row):
        self.main_prog = main_prog
        super().__init__(row)
        if "k" in row:
            self.k = row["k"]
            if isinstance(self.k, str):
                self.k = eval(self.k)
        self.target_size = None
        self.iterations = 0
        if row.get("iterations"):
            _, self.iterations = main_prog.eval(str(row.get("iterations")))

        if row.get("target"):
            _, self.target = main_prog.eval(str(row.get("target")))
        self.formula = row['formula']
        self.condition = None
        self._parse_exponent()

    def _gen_formula(self, value):
        return self.base_regex.sub(r'\g<1>{}'.format(value) if self.has_prefix else r'{}'.format(self.base), self.formula, count=1)

    def __next__(self):
        if self.target and ((self.result + eval(self.base_formula)) < self.target) or (self.iterations and self.current_iteration < self.iterations):
            self.current_iteration += 1 if not self.k else self.k
            return self.current_iteration
        else:
            raise StopIteration

    def _compute(self):
        value = eval(self.formula)
        if self.iterations:
            self.result = self.iterations * value
            self.current_iteration = self.iterations
        elif self.target:
            self.current_iteration = self.target // value
            if self.current_iteration == 0:
                raise Exception("Formula result, {} , is greater than target: {} > {}".format(
                    self.base_formula, my_hex(self.target), my_hex(value)))
            self.result = self.current_iteration * value

    def compute(self):
        self._compute()
        x = symbols('x')
        expr_deriv = self._gen_formula(value='x')
        first_deriv = diff(eval(expr_deriv))
        second_deriv = diff(eval(expr_deriv), x, x)
        return first_deriv, second_deriv

    def should_record_computation(self, current_iteration, result):
        return True

class FormulaRaiseExponent(FormulaParserUnstructured):
    MAX_EXPONENT = 21

    def __init__(self, main_prog, row):
        super().__init__(main_prog, row)
        self.raise_exp_times = min(int(row["raise exponent"]), self.MAX_EXPONENT)

    def __next__(self):
        if not self.current_iteration:
            self.current_iteration += 1
            return self.current_iteration
        else:
            raise StopIteration

    def _compute(self):
        self.result = eval(self.formula)
        stack = []
        for i in range(self.raise_exp_times):
            if self.target and self.result > self.target:
                break
            if self.main_prog.is_debug:
                t0 = timeit.default_timer()
            self.result = pow(self.result, self.exponent)
            self.formula = "({})**{}".format(self.formula, self.exponent)
            stack.append([self.result, self.formula])
            if self.main_prog.is_debug:
                self.main_prog.logger.debug("{} raise exp: {} length: {}".format(self.base, i + 1, len(str(self.result))))
                elapsed_time = timeit.default_timer() - t0
                self.main_prog.logger.debug('Calculation took {:.3f} seconds'.format(elapsed_time))
        if self.target and type(self.target) != Decimal and abs(self.result - self.target) > self.target and len(stack) > 1:
            self.result, self.formula = stack[-2]


class FormulaIncBaseAfterKiteraions(FormulaParserUnstructured):
    def __init__(self, main_prog, row):
        super().__init__(main_prog, row)
        self.increment = int(row.get("increment", 0))

    def _compute(self):
        base = eval(self.formula)
        self.result += base * self.k

    def __next__(self):
        if self.current_iteration:
            if self.increment and self.current_iteration % self.k == 0:
                self.base += self.increment
                self.formula = self._gen_formula(value=self.base)
        if self.target and ((self.result + eval(self.base_formula)) < self.target) or (self.iterations and self.current_iteration < self.iterations):
            self.current_iteration += self.k
            return self.current_iteration
        else:
            raise StopIteration


class FormulaStopUntilTargetSize(FormulaParserUnstructured):
    def __init__(self, main_prog, row):
        super().__init__(main_prog, row)

        def extract_msb_lsb(v):
            parts = v.split("|")
            parts[0] = parts[0][len("size_of_"):]
            _, n = main_prog.eval("|".join(parts))
            return msb(n), n & main_prog.BIT_MASK
        _, self.target_size = main_prog.eval(row['target_size'])
        self.target_msb, self.target_lsb = extract_msb_lsb(row['target_size'])
        size_of_iteration_path = row['target_size'].replace("size_of_result", "size_of_iteration")
        _, self.iter_size = main_prog.eval(size_of_iteration_path)
        self.iter_msb, self.iter_lsb = extract_msb_lsb(size_of_iteration_path)
        self.match_lsb = False

    def __next__(self):
        if not self.current_iteration:
            self.current_iteration += 1
            return self.current_iteration
        else:
            raise StopIteration

    def _compute(self):
        self.main_prog.find_iterations(formula_parser=self)


class FormulaCustom(FormulaParserUnstructured):

    def _make_lambda(self, s):
        return eval("lambda x: {}".format(s.format("x")))

    def __init__(self, main_prog, row, start=None, end=None):
        super().__init__(main_prog, row)

        self.target_condition = None
        if 'start' in row:
            _, self.result = main_prog.eval(row['start'])
        if 'target_condition' in row:
            self.target_condition = self._make_lambda(row['target_condition'])
        if 'condition' in row:
            self.condition = self._make_lambda(row['condition'])
        else:
            self.condition = self.target_condition
        self.base_value = eval(self.formula)
        if start:
            self.current_iteration = start
            self.start = start
            self.result += (start * self.base_value)
            self.iterations = end

        self.end = end or self.iterations

    def __next__(self):
        if self.target_condition and self.target_condition(self.result):
            raise StopIteration
        return super().__next__()

    def _compute(self):
        self.result += (self.base_value if not self.k else self.k)

    def should_record_computation(self, current_iteration, result):
        return (self.condition and self.condition(result)) \
            or current_iteration == self.iterations \
            or self.should_log() \
            or self.main_prog.exit_sig_hdlr.terminate

class FormulaTargetLSB(FormulaStopUntilTargetSize):
    def __init__(self, main_prog, row):
        super().__init__(main_prog, row)
        self.match_lsb = True


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
            "log_base": my_hex(base),
            "log_value": my_hex(computed_value),
            "result": result,
            "run_date": run_date
        }
        self.mongo_db.computation.update_one({"filename": computation['filename']}, computation, upsert=True, multi=False)

        my_print(result)
        return result

    def find_lsb(self, r, base, formula_parser, iterations):
        num_bytes, low_iters = gen_bytes(formula_parser.iter_size - 1)
        mid_iters = max(256**(num_bytes + 1), low_iters)
        msb_value = msb(mid_iters, 4)
        if self.options.config.get("compute_optimal_number_of_cpu_threads"):
            num_of_threads = multiprocessing.cpu_count()
        else:
            num_of_threads = self.options.config.get("threads", 8)

        def gen_result(mid_point, base_result=None, base=None):
            return mid_point

        def find_lsb(r, target_msb, target_lsb, target_size, base, f=lambda a: a + 1, validate=None):
            global max_value

            chunk = self.options.config.get("chunk", 10**8)
            j = 0
            iterations = None
            while not iterations:
                self.logger.debug("Iteration {}".format(j + 1))
                r += (j * num_of_threads * chunk * base)
                max_value = r + (num_of_threads * chunk * base)
                self.logger.debug("j({}) chunk({}) * num_of_threads({}) * base: {}".format(j, chunk, num_of_threads, hex(r)))

                if bytes_needed(r) != target_size or msb(r) != target_msb:
                    break
                with concurrent.futures.ThreadPoolExecutor(max_workers=num_of_threads) as executor:
                    futures_to_id = {executor.submit(_find_lsb, r=r, it=j, thread_num=i, chunk=chunk, target_msb=target_msb, target_lsb=target_lsb,
                                                     target_size=target_size, base=base, f=f, validate=validate): i for i in range(num_of_threads)}
                j += 1
                for future in concurrent.futures.as_completed(futures_to_id):
                    _id = futures_to_id[future]
                    try:
                        result = future.result()
                        if result and not iterations:
                            iterations = result
                    except Exception as exc:
                        msg = '%r generated an exception: %s' % (_id, exc)
                        self.logger.exception(msg)
            if not iterations:
                raise Exception("Failed to find target lsb {}".format(target_lsb))
            return iterations

        def _find_lsb(r, it, thread_num, chunk, target_msb, target_lsb, target_size, base, f=lambda a: a + 1, validate=None):

            r += (thread_num * chunk * base)
            self.logger.debug("thread({}): start {}".format(thread_num, hex(r)))

            num_iters = self.options.config.get("sample_rate", 10**6)
            for i in range(chunk):
                if i > 0 and (msb(r, 4) != target_msb):
                    break
                if r & Calculator.BIT_MASK == target_lsb:
                    if not validate or validate(i):
                        self.logger.debug("found lsb {}:{}".format(hex(target_lsb), i))
                        return i
                i = f(i)
                if i % num_iters == 0:
                    size = bytes_needed(r)
                    if size != target_size:
                        raise Exception("byte size {} does not match {}".format(size, target_size))
                    self.logger.debug("iteration {}, thread {}, find_target: {} lsb: {} r: {} i: {}".format(
                        it, thread_num, hex(target_lsb), hex(r & Calculator.BIT_MASK), hex(r), i))
                r += base
            self.logger.debug("thread({}): i({}) * base: {}".format(thread_num, i, hex(r)))
            if r > max_value:
                raise Exception("thread({}) r{} exceeded max_value {}".format(thread_num, r, max_value))
            return None

        find_target_lsb = True

        def _is_valid(r, msb, lsb):
            ok = r & Calculator.BIT_MASK == formula_parser.iter_lsb and msb(r) == formula_parser.iter_msb
            self.logger.debug("Validating {} target_lsb {}: {}".format(hex(r), hex(formula_parser.target_msb), "ok" if ok else "not ok"))
            return ok

        if find_target_lsb:

            def is_valid(i):
                r = i + iterations
                sz = bytes_needed(r)
                if sz == formula_parser.iter_size:
                    return _is_valid(r, msb=formula_parser.iter_msb, lsb=formula_parser.iter_lsb)
                else:
                    self.logger.debug("Expected size {} but got {}".format(formula_parser.iter_size, sz))
                    return False

            more_iterations = find_lsb(r, target_msb=formula_parser.target_msb, target_lsb=formula_parser.target_lsb,
                                       target_size=formula_parser.target_size, base=base, validate=is_valid)
            if not more_iterations:
                more_iterations = find_lsb(r, target_msb=formula_parser.target_msb, target_lsb=formula_parser.target_lsb,
                                           target_size=formula_parser.target_size, base=base, f=lambda a: a - 1, validate=is_valid)
            if not more_iterations:
                raise Exception("Did not find lsb base {}".format((hex(formula_parser.target_lsb))))
            return more_iterations + iterations

        iters = mid_iters
        if msb_value != formula_parser.iter_msb:
            iters = None
            if low_iters != mid_iters and msb(mid_iters) > formula_parser.target_msb:
                iters = self.find_msb(low=low_iters, high=mid_iters, calc=gen_result, target_size=formula_parser.iter_size,
                                      target_msb=formula_parser.iter_msb, base_result=None, base=None)
            if not iters:
                high_iters = max(256**(num_bytes + 2), low_iters)
                iters = self.find_msb(low=mid_iters + 1, high=high_iters, calc=gen_result,
                                      target_size=formula_parser.iter_size, target_msb=formula_parser.iter_msb, base_result=None, base=None)
        if iters:
            def is_valid(i):
                r = base * i
                return _is_valid(r, msb=formula_parser.target_msb, lsb=formula_parser.target_lsb)

            iterations = find_lsb(r=iters, target_msb=formula_parser.iter_msb, target_lsb=formula_parser.iter_lsb,
                                  target_size=formula_parser.iter_size, base=1, f=lambda a: a + 1, validate=is_valid)
            if iterations:
                return iterations
            iterations = find_lsb(r=iters, target_msb=formula_parser.iter_msb, target_lsb=formula_parser.target_lsb,
                                  f=lambda a: a - 1, target_size=formula_parser.target_size, base=1, validate=is_valid)
            return iterations

        raise Exception("Did not find lsb base {}".format((hex(formula_parser.target_lsb))))

    def find_msb(self, low, high, calc, target_size, target_msb, base_result=None, base=None,):
        num_iters = 1
        j = 0
        diff = high - low
        while low <= high:
            j += 1
            mid_point = (high + low) // 2
            r = calc(mid_point, base_result, base)
            msb_value = msb(r, 4)
            found = msb_value == target_msb
            if found:
                return mid_point
            if j % num_iters == 0:
                #                 diff_previous = diff - (high - low)
                #                 diff = high - low
                #print("iteration: {}, diff_from_previous: {}, diff: {}, size: {}, max_size: {}".format(j, hex(diff_previous), hex(high - low), size, formula_parser.target_size))
                #print("iteration: {}, low: {}, high: {}, diff: {}, size: {}, max_size: {}".format(j, hex(low), hex(high), high-low, bytes_needed(r), formula_parser.target_size))
                self.logger.debug("midpoint msb: {}, target msb: {}".format(hex(msb(r)), hex(target_msb)))

            size = bytes_needed(r)
            if (size == target_size and msb_value > target_msb) or size > target_size:
                high = mid_point - 1
                if j % num_iters == 0:
                    self.logger.debug("setting high to midpoint, low: {}, high: {}".format(hex(low), hex(high)))
            else:
                low = mid_point + 1
                if j % num_iters == 0:
                    self.logger.debug("setting low to midpoint, low: {}, high: {}".format(hex(low), hex(high)))

    def find_iterations2(self, formula_parser):
        base = eval(self.base_formula)
        _, iterations = gen_bytes(formula_parser.target_size - (bytes_needed(base) - 1))
        result = iterations * (base)
#         i = 0
#         while True:
#             i -= 1
#             result -= (16**16)
#             if abs(i) % 1000000 == 0:
#                 self.logger.debug("examined {} values: bytes_needed {}: {}".format(abs(i), bytes_needed(result), hex(result)))
#
#             if bytes_needed(result) < formula_parser.target_size:
#                 break
#         result += (16**16)
#         iterations-= (i -1)
        formula = "(16**16) * {}".format(iterations)
        return iterations, formula, result

    def find_iterations(self, formula_parser, match_lsb=False):
        base_formula = formula_parser.formula
        base = eval(base_formula)
        mult, iterations = gen_bytes(formula_parser.target_size - bytes_needed(base) - 1)
        result = iterations * base
        formula = "{} * (256 ** {})".format(base_formula, mult)
        self.logger.debug("low bytes: {}".format(bytes_needed(result)))
        base_formula = formula
        mid_iterations = (256 ** (mult + 1)) - iterations
        mid_result = (256 ** (mult + 1)) * base
        self.logger.debug("mid bytes: {}".format(bytes_needed(mid_result)))
        self.logger.debug("iterations: {}".format(hex(iterations)))
        msb_value = msb(mid_result, 4)

        def gen_result(mid_point, base_result, base):
            return base_result + (mid_point * base)

        if msb_value == formula_parser.target_msb:
            if match_lsb:
                iters = mid_iterations
            else:
                lsb_iterations = self.find_lsb(mid_result, base=base, formula_parser=formula_parser, iterations=iterations + mid_iterations)
                return lsb_iterations
        else:
            iters = self.find_msb(low=0, high=mid_iterations, calc=gen_result, base_result=result, base=base,
                                  target_size=formula_parser.target_size, target_msb=formula_parser.target_msb)
            if not iters:
                high_iterations = (256 ** (mult + 2)) - iterations
                high_result = (256 ** (mult + 2)) * base
                self.logger.debug("high bytes: {}".format(bytes_needed(high_result)))
                iters = self.find_msb(low=mid_iterations, high=high_iterations, calc=gen_result, base_result=result,
                                      base=base, target_size=formula_parser.target_size, target_msb=formula_parser.target_msb)
        if not iters:
            raise Exception("Could not find target number of iterations")
        result += iters * base
        formula_parser.result = result
        if match_lsb:
            lsb_iterations = self.find_lsb(result, base=base, formula_parser=formula_parser, iterations=iterations + iters)
            formula_parser.current_iteration = lsb_iterations
        else:
            formula_parser.current_iteration = iterations + iters

    def store_computation_wrapper(self, thread_num):
        WAIT_TIME = .25
        name = threading.current_thread().name
        self.logger.debug('Starting thread - {}'.format(name))
        while not self.start_event.is_set():
            self.start_event.wait(WAIT_TIME)
        while True:
            try:
                filename, run_date, current_iteration, result, formula_parser, first_deriv, second_deriv, elapsed_time, elapsed_iterations, should_record = self.queue.get(timeout=2)
                self.store_computation(filename, run_date, current_iteration, result, formula_parser, first_deriv, second_deriv, elapsed_time, elapsed_iterations, should_record)
                if self.exit_sig_hdlr.terminate:
                    break
            except Empty:
                if self.computation_finished or self.exit_sig_hdlr.terminate:
                    break
            except Exception:
                self.logger.exception("Failed to store iteration: {}, formula: {}, result: {}".format(
                    current_iteration, formula_parser.base_formula, my_hex(result)))
        self.queue.task_done()
        self.logger.debug('Exiting thread - {}'.format(name))

    def _make_computation(self, filename, run_date, current_iteration, result, formula_parser, first_deriv, second_deriv, elapsed_time, elapsed_iterations):
        istr = my_hex(current_iteration)
        str_result = my_hex(result)

        computation = {"filename": filename, "iteration": istr,
                       "size_of_iteration": bytes_needed(current_iteration),
                       "len_of_iteration": len(istr),
                       "formula": formula_parser.formula,
                       "result": str_result,
                       "size_of_result": bytes_needed(result),
                       "len_of_result": len(str_result),
                       "first_derivative": str(first_deriv),
                       "second_derivative": str(second_deriv),
                       "run_date": run_date,
                       "insert_date": datetime.now(timezone.utc)}
        if elapsed_time:
            computation["elapsed_{}".format(timer.precision_text)]= my_hex(elapsed_time)
            computation["elapsed_iterations"] = my_hex(elapsed_iterations)
        if formula_parser.k:
            computation['k'] = my_hex(formula_parser.k)
        if self.options.args.tag:
            computation['tag'] = self.options.args.tag
        if formula_parser.iterations:
            computation['target_iterations'] = my_hex(formula_parser.iterations)
            computation["size_of_target"] = bytes_needed(formula_parser.iterations)
            computation["len_of_target"] = len(computation['target_iterations'])
            distance_from_target = formula_parser.iterations - current_iteration
            computation['distance_from_target_iterations'] = my_hex(distance_from_target)
            computation["size_of_distance_from_target_iterations"] = bytes_needed(abs(distance_from_target))
            computation["len_of_distance_from_target_iterations"] = len(computation['distance_from_target_iterations'])          
        if formula_parser.target:
            computation['target'] = my_hex(formula_parser.target)
            computation["size_of_target"] = bytes_needed(formula_parser.target)
            computation["len_of_target"] = len(computation['target'])
            distance_from_target = formula_parser.target - result
            computation['distance_from_target'] = my_hex(distance_from_target)
            computation["size_of_distance_from_target"] = bytes_needed(abs(distance_from_target))
            computation["len_of_distance_from_target"] = len(computation['distance_from_target'])
        return computation

    def store_computation(self, filename, run_date, current_iteration, result, formula_parser, first_deriv, second_deriv, elaspsed_time, elapsed_iterations, should_record):
        if should_record:
            computation = self._make_computation(filename, run_date, current_iteration, result,
                                                 formula_parser, first_deriv, second_deriv, elaspsed_time, elapsed_iterations)
            if self.is_info:
                self.logger.info("Match: {}".format(computation))
            try:
                self.mongo_db.computation.insert_one(computation)
            except:
                self.logger.exception("Failed to store document: {}".format(computation))
                distance_from_target = computation['distance_from_target']
                del computation['distance_from_target']
                self.mongo_db.computation.insert_one(computation)
                self.logger.warn("Removed distance_from_target {}.".format(distance_from_target))
        else:
            computation = self._make_computation(filename, run_date, current_iteration, result,
                                                 formula_parser, first_deriv, second_deriv, elaspsed_time, elapsed_iterations)
            self.logger.debug("No match: {}".format(computation))

    @timing_logit
    def execute_formula(self, filename, num_of_io_threads, run_date, formula_parser):
        it = iter(formula_parser)
        formula_parser.start_time = timer.timer()
        while next(it, None) and not self.exit_sig_hdlr.terminate:
            try:
                first_deriv, second_deriv = formula_parser.compute()
                should_record = formula_parser.should_record_computation(formula_parser.current_iteration, formula_parser.result)
                if should_record or self.is_debug:
                    elaspsed_time, elapsed_iterations = formula_parser.measure_elapsed_time()
                    if num_of_io_threads > 0:
                        self.queue.put((filename, run_date, formula_parser.current_iteration, formula_parser.result,
                                        formula_parser, first_deriv, second_deriv, elaspsed_time, elapsed_iterations, should_record))
                    else:
                        self.store_computation(filename, run_date, formula_parser.current_iteration, formula_parser,
                                               first_deriv, second_deriv, elaspsed_time, elapsed_iterations, should_record)
            except:
                self.logger.exception("Failed to process iteration: {}, formula: {}, result: {}".format(
                    formula_parser.current_iteration, formula_parser.base_formula, my_hex(formula_parser.result)))
        self.logger.info("Completed execute formula: number of iterations: {}, target iterations: {}".format(
            hex(formula_parser.current_iteration), hex(formula_parser.iterations)))
        if formula_parser.k:
            self.logger.info("Completed execute formula: number of computations: {}".format(
                hex(formula_parser.current_iteration // formula_parser.k)))

    def retrieve_computed_result(self, filename, field="formula"):
        r = list(self.mongo_db.computation.find({"filename": filename}).sort(([('_id', -1)])).limit(1))
        if r:
            # result is default
            value = r[0][field]
            if field != 'formula' and isinstance(value, str):
                value = eval(value)
            self.logger.debug("Retrieving {} of computed result for {}".format(field, filename))
            if field in ['formula', 'expression']:
                value = "({})".format(value)
            return value
        raise Exception("{} has not been computed".format(filename))

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
            formula_parser = FormulaFactory.make_formula(main_prog=self, row=row)
            self.mongo_db.computation.delete_one({"filename": filename})
            if num_of_io_threads:
                with concurrent.futures.ThreadPoolExecutor(max_workers=num_of_io_threads) as executor:
                    self.computation_finished = False
                    futures_to_id = {executor.submit(self.store_computation_wrapper,  thread_num=i): i for i in range(num_of_io_threads)}
                    self.start_event.set()
                    self.execute_formula(filename, num_of_io_threads, run_date, formula_parser)
                    self.computation_finished = True
                    for future in concurrent.futures.as_completed(futures_to_id):
                        _id = futures_to_id[future]
                        try:
                            future.result()
                        except Exception as exc:
                            msg = '%r generated an exception: %s' % (_id, exc)
                            self.logger.exception(msg)
            else:
                self.execute_formula(filename, num_of_io_threads, run_date, formula_parser)

        return formula_parser.result

    def compute_gauss_summation(self):
        s = self.options.args.gauss_summation

        getcontext().prec = 1000
        r = Decimal((1 + (8 * s)))
        ir = r.sqrt()
        result = (-1 + ir) / 2, (-1 - ir) / 2

        computation = {
            "filename": "gauss_{}".format(s),
            "result": my_hex(result[0]),
            "size_of_result": bytes_needed(result[0]),
            "run_date": datetime.utcnow()
        }
        self.mongo_db.computation.update_one({"filename": computation['filename']}, computation, upsert=True, multi=False)
        my_print(computation['result'])
        return result

    def get_computed_result(self, operand, field="formula"):
        if operand.endswith(".csv"):
            f = operand.split("|", maxsplit=1)
            if len(f) > 1:
                operand = f[1]
                field = f[0]
            value = self.retrieve_computed_result(filename=operand, field=field)
            return value
        if operand.endswith(".txt"):
            with open(operand, "r") as f:
                s = f.read()
                value = int(s)
                return value
        if operand.endswith(".bin"):
            with open(operand, "rb") as f:
                s = f.read()
                value = int.from_bytes(s, byteorder='big')
                return value
                #self.target = numpy.fromfile(f, dtype=numpy.int, count=-1)
        return None

    def eval(self, s):
        result = None
        getcontext().prec = 1000000
        operand_regex = regex.compile("(.*?)([0-9a-hx]+)", flags=regex.IGNORECASE)
        path_regex = regex.compile(r"(.*?)([_a-z0-9|/]{4,}\.[a-z]{3,})", flags=regex.IGNORECASE)
        start_pos = 0
        expr = ""
        evaluated = False
        while start_pos < len(s):
            match_operand = operand_regex.match(s[start_pos:])
            match_path = path_regex.match(s[start_pos:])
            if not match_operand and not match_path:
                expr += s[start_pos:]
                break
            operand = match_operand.group(2) if match_operand else ""
            path = match_path.group(2) if match_path else ""
            if operand and len(operand) >= len(path):
                try:
                    start, end = match_operand.span()
                    start += start_pos
                    end += start_pos
                    expr += s[start:end]
                except:
                    pass
            elif path:
                value = self.get_computed_result(path)
                if not value:
                    self.logger.error("Failed to evaluate operand {} of {}".format(path, s))
                    return
                start, end = match_path.span()
                start += start_pos
                end += start_pos
                expr += (match_path.group(1) + str(value))
            start_pos = end
#         if len(expr) > 500000:
#             r = expr.split()
#             if r and len(r) == 3:
#                 evaluated = True
#                 op1 = Decimal(eval(r[0]))
#                 op2 = Decimal(eval(r[2]))
#                 if r[1] == '*':
#                     result = Decimal(op1 * op2)
#                 elif r[1] == '/':
#                     result = Decimal(op1 / op2)
#                 elif r[1] == '//':
#                     result = Decimal(op1 // op2)
#                 elif r[1] == '+':
#                     result = Decimal(op1 + op2)
#                 elif r[1] == '-':
#                     result = Decimal(op1 - op2)
#                 elif r[1] == '%':
#                     result = Decimal(op1 % op2)
#                 else:
#                     evaluated = False
        if not evaluated:
            result = eval(expr)
        return expr, result

    def evaluate_expr(self):
        if not self.options.args.name:
            raise Exception("-n is required for -e option")
        s = self.options.args.eval
        expr, result = self.eval(s)

        if type(result) == Decimal:
            if result % 1 == 0:
                result = int(result)

        r = my_hex(result)
        computation = {
            "formula": self.options.args.eval,
            "filename": self.options.args.name,
            "expression": expr,
            "result": r,
            "size_of_result": bytes_needed(result),
            "run_date": datetime.utcnow()
        }
        if self.options.args.tag:
            computation['tag'] = self.options.args.tag
        self.mongo_db.computation.update_one({"filename": computation['filename']}, computation, upsert=True, multi=False)

        my_print(r)
        return result

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

    def validate_tagged_results(self):
        tag = self.options.args.validate_tagged_results
        r = None
        for i, computation in enumerate(self.mongo_db.computation.find({"tag": tag}).sort(([('_id', -1)]))):
            f = eval(computation['formula'])
            iters = eval(str(computation['iteration']))
            r = (f * iters) + eval(computation['distance_from_target'])
            self.logger.debug("{}: ({} * {}) + {}".format(i, computation['formula'],
                                                          computation['iteration'], computation['distance_from_target']))
            self.logger.debug("comparing {} and  {}".format(computation['target'], my_hex(r)))
            assert eval(computation['target']) == r
            self.logger.debug("Equal")

    def process(self):
        commands = {"gauss_summation": self.compute_gauss_summation,
                    "log_command_file": self.compute_log,
                    "filename": self.process_csv,
                    "eval": self.evaluate_expr,
                    "validate_tagged_results": self.validate_tagged_results}
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
