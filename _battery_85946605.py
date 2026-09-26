def flatten(nested):
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result

assert flatten([[1, 2], [3], [4, 5]]) == [1, 2, 3, 4, 5]
