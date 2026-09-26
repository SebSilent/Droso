def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

assert [fib(i) for i in range(8)] == [0, 1, 1, 2, 3, 5, 8, 13]
