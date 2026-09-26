def safe_div(a, b):
    if b == 0:
        return None
    return a / b

assert safe_div(6, 3) == 2
assert safe_div(1, 0) is None
