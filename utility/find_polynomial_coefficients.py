import numpy as np

# Your data points (x) and the large numbers/targets you want to approximate (y)
x = np.array([1, 2, 3, 4, 5])
y = np.array([10123, 20456, 40912, 81824, 163648])

# Fit a 2nd-degree polynomial: P(x) = c2*x^2 + c1*x + c0
# polyfit uses a linear least-squares algorithm via SVD/QR decomposition
coefficients = np.polyfit(x, y, deg=2)

print("Polynomial coefficients (highest degree first):", coefficients)

def residual_to_zigzag(error):
    """Maps a signed residual to a strictly positive integer."""
    if error >= 0:
        return error * 2
    else:
        return (abs(error) * 2) - 1

def zigzag_to_residual(z_number):
    """Reverses the mapping back to the signed residual."""
    if z_number % 2 == 0:
        return z_number // 2
    else:
        return -((z_number + 1) // 2)

# Quick verification test
sample_residuals = [-3, 0, 4, -1]
mapped_numbers = [residual_to_zigzag(r) for r in sample_residuals]

print(f"Original Signed Residuals: {sample_residuals}")
print(f"Mapped Positive Numbers:   {mapped_numbers}")