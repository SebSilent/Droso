def dedupe(items):
    return list(dict.fromkeys(items))

assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]
