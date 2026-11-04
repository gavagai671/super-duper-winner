# import numpy as np
# from numpy.polynomial import Polynomial
#
# # Define an arbitrary complexity (e.g., degree 10)
# degree = 10 
#
# # Generate random coefficients (constant up to x^10)
# random_coefficients = np.random.uniform(-10, 10, size=degree + 1)
#
# # Create the polynomial object
# poly = Polynomial(random_coefficients)
#
# print(poly)


# import matplotlib
#
# matplotlib.use('TkAgg') 
#
# from collections import Counter
# import matplotlib.pyplot as plt
#
#
# # 1. Sample data: A Counter object representing item frequencies
# data_counter = Counter(['apple', 'banana', 'apple', 'orange', 'banana', 'apple', 'grape'])
#
# # 2. Extract keys (items) and values (counts)
# labels, counts = zip(*data_counter.items())
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
# Output: Polynomial([-4.2 + 8.1·x - 1.2·x² + ... + 3.7·x¹⁰])


# The maximum value for an unsigned 18-bit integer is 262,143
MASK_18_BIT = (1 << 18) - 1  # 0x3FFFF (or 262143)

# Example: Start near the overflow boundary and increment
max_val = 262142

current_val = max_val + 1

for _ in range(100):
    # Increment by 1 bit value and enforce the 18-bit limit
    current_val = (current_val + 1) & MASK_18_BIT
    print(f"Decimal: {current_val:6} | Binary: {current_val:018b}")

    
    
    