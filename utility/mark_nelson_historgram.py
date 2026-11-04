import matplotlib
from contourpy import chunk

matplotlib.use('TkAgg') 

from collections import Counter, defaultdict

fn = "data/AMillionRandomDigits.bin"

with open(fn, "rb") as f:
    s = f.read()

chunk_size = 18
max_display = 20

MASK_18_BIT = (1 << chunk_size) - 1  # 0x3FFFF (or 262143)

max_value = 2 ** chunk_size

data_counter = Counter()

current_val = max_value - 1

for _ in range(max_value):
    # Increment by 1 bit value and enforce the 18-bit limit
    current_val = (current_val + 1) & MASK_18_BIT
    data_counter[f"{current_val:018b}"] = 0
    # print(f"Decimal: {current_val:6} | Binary: {current_val:018b}")

chunk_string = ""

for b in s[:(max_value // 8)]:
    bit_string = f"{b:08b}"
    if len(chunk_string) + 8 <= chunk_size:
        chunk_string += bit_string
    else:
        size_needed = chunk_size - len(chunk_string)
        chunk_string += bit_string[:size_needed]
        data_counter.update([chunk_string])
        chunk_string = bit_string[size_needed:]           

# 1. Sample data: A Counter object representing item frequencies

# 2. Sort the unique items:
# Primary key: -x[1] (Frequency descending)
# Secondary key: x[0] (Value ascending)
sorted_summary = sorted(data_counter.items(), key=lambda x: (-x[1], x[0]))
# Step 1: Group items by their frequency
frequency_groups = defaultdict(list)
for item, freq in data_counter.items():
    frequency_groups[freq].append(item)

# Step 2: Print grouped items sorted by the frequency number
print("Items grouped by frequency in descending order:")
for freq in sorted(frequency_groups.keys(), reverse=True):
    print(f"Frequency {freq}: {len(frequency_groups[freq])}")

print(f"\nTop {max_display} items by frequency in descending order, bit_strings are in ascending order:")
for item, count in sorted_summary[:max_display]:
    print(f"Item: {item} | Count: {count}")

print(f"\nBottom {max_display} items  sorted by value in ascending order")
for item, count in [(item, count) for item, count in sorted_summary if count == 0][:max_display]:
    if count == 0:
        print(f"Item: {item} | Count: {count}")

# import matplotlib.pyplot as plt

# 2. Extract keys (items) and values (counts)
# labels, counts = zip(*frequent_counts.items())
#
# size_to_display = 50
#
# labels =labels[:size_to_display]
# counts =counts[:size_to_display]
#
# # 3. Plot using a bar chart
# plt.figure(figsize=(8, 5))
# plt.bar(labels, counts, color='skyblue', edgecolor='black')
#
# plt.title('Frequency Distribution from Counter')
# plt.xlabel('Items')
# plt.ylabel('Counts')
# plt.grid(axis='y', alpha=0.3)
#
# plt.show()
# # Showing first 8 bits (letter 'a')
#

