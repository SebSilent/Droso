def chunk(items, n):
    return [items[i:i + n] for i in range(0, len(items), n)]

assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
