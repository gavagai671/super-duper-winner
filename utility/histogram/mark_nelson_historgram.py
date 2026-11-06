import math
import os
from collections import Counter, defaultdict
import logging
from pymongo import MongoClient as Client
from utility.generic_config import GenericConfig, Logger
from gridfs.grid_file_shared import DEFAULT_CHUNK_SIZE


DEFAULT_CHUNK_SIZE=18
DEFAULT_DISPLAY_SIZE=300

def binary_string_to_hex(binary_str):
    # 1. Convert binary string to integer, then integer to hex
    # 2. Use [2:] to slice off the '0x' prefix and upper() for uppercase hex
    hex_str = hex(int(binary_str, 2))[2:].upper()
    
    # 3. Pad with leading zeros to ensure a consistent 5-character width
    hex_str_padded = hex_str.zfill(5)
    return hex_str_padded
                   
class MarkNelsonHistorgramSettings(GenericConfig):

    def add_arguments(self, parser):
        parser.add_argument('-f', '--filename', default="../data/AMillionRandomDigits.bin", required=False, help="binary file of large random digits")


class MarkNelsonHistorgram(object):

    def __init__(self, options):
        self.options = options
        Logger(options=options.log)
        self.logger = logging.getLogger("mark_nelson_historgram")
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
        with open(self.options.args.filename, "rb") as f:
            self.bytestream = f.read()
        self.sections_by_binary_string = {}
        self.global_data_counter = None
        
    def print_sorted_bitstrings(self, keys, data_counter, max_display, is_section):
        
        if is_section:
            print("\nBinary string,Count")
        else:
            print("\nBinary string,Count,Section")
        for binary_string in keys[:max_display]:
            if is_section:
                print(f"{binary_string_to_hex(binary_string)},{data_counter[binary_string]}")
            else:
                sections = ' '.join(str(num) for num in sorted(self.sections_by_binary_string[binary_string])) if binary_string in self.sections_by_binary_string else ''
                print(f"{binary_string_to_hex(binary_string)},{data_counter[binary_string]},{sections}")      
                
    def process(self):
        num_of_chunks = math.ceil(os.path.getsize(self.options.args.filename)/(2**18//8))
        for i in range(num_of_chunks):
            self.process_section(section=i)
        #self.process_section(section=3, chunk_size=17)
        self.process_section()
        
    
    def process_section(self, chunk_size=DEFAULT_CHUNK_SIZE, max_display=DEFAULT_DISPLAY_SIZE, section=None):
        
        MASK_18_BIT = (1 << chunk_size) - 1  # 0x3FFFF (or 262143)
        max_value = 2 ** chunk_size
        current_val = max_value - 1
            
        if self.global_data_counter is None:
            self.global_data_counter = Counter()
            for _ in range(max_value):
                # Increment by 1 bit value and enforce the 18-bit limit
                current_val = (current_val + 1) & MASK_18_BIT
                self.global_data_counter[f"{current_val:018b}"] = 0   
    
        if section is not None:
        

            data_counter = Counter()
            
            
            for _ in range(max_value):
                # Increment by 1 bit value and enforce the 18-bit limit
                current_val = (current_val + 1) & MASK_18_BIT
                data_counter[f"{current_val:018b}"] = 0
                
                # print(f"Decimal: {current_val:6} | Binary: {current_val:018b}")
            
            chunk_string = ""
            
            start = section * (max_value // 8)
                     
            for b in self.bytestream[start:start + (max_value // 8)]:
                binary_string = f"{b:08b}"
                if len(chunk_string) + 8 <= chunk_size:
                    chunk_string += binary_string
                else:
                    size_needed = chunk_size - len(chunk_string)
                    chunk_string += binary_string[:size_needed]
                    data_counter.update([chunk_string])
                    self.global_data_counter.update([chunk_string])
                    if chunk_string not in self.sections_by_binary_string:
                        self.sections_by_binary_string[chunk_string] = set()
                    self.sections_by_binary_string[chunk_string].add(section)
                    chunk_string = binary_string[size_needed:]     
        else:
            data_counter = self.global_data_counter      
            
        #self.global_data_counter += data_counter

        
        # 1. Sample data: A Counter object representing item frequencies
        
        # 2. Sort the unique items:
        # Primary key: -x[1] (Frequency descending)
        # Secondary key: x[0] (Value ascending)
        sorted_summary = sorted(data_counter.items(), key=lambda x: (-x[1], x[0]))
        # Step 1: Group items by their frequency
        frequency_groups = defaultdict(list)
        for item, freq in data_counter.items():
            frequency_groups[freq].append(item)
        
        if section is not None:
            print(f"\n\nProcessing section {section}")
        else:
            print(f"\n\nProcessing entire data stream")
    
        # Step 2: Print grouped items sorted by the frequency number
        print("\nItems grouped by frequency in descending order:")
        print("\n\nFrequency,Count")
        for freq in sorted(frequency_groups.keys(), reverse=True):
            print(f"{freq},{len(frequency_groups[freq])}")
            
        #print(f"\nTotal number of items: {sum(len(frequency_groups[freq]) for freq in frequency_groups.keys())}")
        print(f"\nTotal number of nonzero binary_strings: {data_counter.total()}")
          
        print(f"\nTop {max_display} sorted by frequency in descending order, binary strings are in ascending order:")
        
        print("\n\nBinary_string,Count")
        for binary_string, count in sorted_summary[:max_display]:
            print(f"{binary_string_to_hex(binary_string)},{count}")
        
        keys = sorted(list(data_counter.keys()))
                
        print(f"\n\nTop {max_display} binary strings sorted by value in ascending order")
        
        self.print_sorted_bitstrings(keys, data_counter, max_display, is_section=section is not None)

        keys = sorted(keys, reverse=True)
        print(f"\n\nBottom {max_display} binary strings sorted by value in descending order")

        self.print_sorted_bitstrings(keys, data_counter, max_display, is_section=section is not None)
            
if __name__ == '__main__':
    options = MarkNelsonHistorgramSettings()
    o = MarkNelsonHistorgram(options)
    o.process()

