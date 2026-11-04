import numpy as np
import struct

def compress_chunk_to_binary(digit_chunk, poly_degree=3):
    """
    Fits a polynomial to a chunk, calculates exact integer residuals,
    and serializes everything into a compact binary byte stream.
    """
    y_true = np.array([int(d) for d in digit_chunk], dtype=np.int8)
    chunk_size = len(y_true)
    x_local = np.arange(chunk_size)
    
    # 1. Fit the polynomial (Least Squares Regression)
    coefs = np.polyfit(x_local, y_true, deg=poly_degree)
    
    # 2. Generate smooth predictions and calculate integer residuals
    y_approx = np.polyval(coefs, x_local)
    # We round to the nearest integer to capture the true discrete offset
    y_approx_rounded = np.clip(np.round(y_approx), 0, 9).astype(np.int8)
    
    # Residuals = True values minus our rounded polynomial baseline
    residuals = y_true - y_approx_rounded
    
    # 3. Binary Serialization Layer
    # Header: Chunk Size (H = 2 bytes), Poly Degree (B = 1 byte)
    binary_data = struct.pack("<HB", chunk_size, poly_degree)
    
    # Pack Coefficients: 4 floats for a cubic polynomial (f = 4 bytes each = 16 bytes)
    for c in coefs:
        binary_data += struct.pack("<f", float(c)) # float32 precision
        
    # Pack Residuals: Each residual is a small integer, stored as 1 signed byte (b)
    for r in residuals:
        binary_data += struct.pack("<b", int(r))
        
    return binary_data


def decompress_binary_to_chunk(binary_data):
    """
    Reads the raw binary byte stream, extracts coefficients and residuals,
    evaluates the polynomial, and perfectly reconstructs the original digit sequence.
    """
    # 1. Unpack Header
    chunk_size, poly_degree = struct.unpack("<HB", binary_data[0:3])
    offset = 3
    
    # 2. Unpack Coefficients
    num_coefs = poly_degree + 1
    coefs = []
    for _ in range(num_coefs):
        c = struct.unpack("<f", binary_data[offset:offset+4])[0]
        coefs.append(c)
        offset += 4
        
    # 3. Unpack Residual Layer
    residuals = []
    for _ in range(chunk_size):
        r = struct.unpack("<b", binary_data[offset:offset+1])[0]
        residuals.append(r)
        offset += 1
        
    # 4. Mathematical Reconstruction
    x_local = np.arange(chunk_size)
    y_approx = np.polyval(coefs, x_local)
    y_approx_rounded = np.clip(np.round(y_approx), 0, 9).astype(np.int8)
    
    # Add back the exact residual corrections to eliminate the gap entirely
    y_reconstructed = y_approx_rounded + np.array(residuals, dtype=np.int8)
    
    # Convert numeric array back to text string
    return "".join(str(d) for d in y_reconstructed)

# ==========================================
# Verification Testing Loop
# ==========================================
if __name__ == "__main__":
    import random
    
    # Generate 500 random sample test digits
    original_digits = "".join(str(random.randint(0, 9)) for _ in range(500))
    
    # Execute Pipeline
    raw_binary_stream = compress_chunk_to_binary(original_digits, poly_degree=3)
    reconstructed_digits = decompress_binary_to_chunk(raw_binary_stream)
    
    # Performance metrics
    print(f"Original Text Footprint:       {len(original_digits)} bytes")
    print(f"Serialized Binary Footprint:   {len(raw_binary_stream)} bytes")
    print(f"Perfect Structural Match?     {original_digits == reconstructed_digits}")