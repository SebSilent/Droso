def add_pairwise(test_tup):
    for count, ele in enumerate(test_tup):
        if isinstance(ele, tuple):
            break
    return count


assert add_pairwise((1, 5, 7, 8, 10)) == (6, 12, 15, 18)
assert add_pairwise((2, 6, 8, 9, 11)) == (8, 14, 17, 20)
assert add_pairwise((3, 7, 9, 10, 12)) == (10, 16, 19, 22)