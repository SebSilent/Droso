def smallest_num(lst):
    minLength = min((len(x) for x in lst))
    return minLength


assert smallest_num([10, 20, 1, 45, 99]) == 1
assert smallest_num([1, 2, 3]) == 1
assert smallest_num([45, 46, 50, 60]) == 45