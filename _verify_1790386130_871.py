def issort_list(n):
    n = str(n)
    if len(n) <= 2:
        return False
    for i in range(2, len(n)):
        if n[i - 2] != n[i]:
            return False
    return True


assert issort_list([1,2,4,6,8,10,12,14,16,17])==True
assert issort_list([1, 2, 4, 6, 8, 10, 12, 14, 20, 17])==False
assert issort_list([1, 2, 4, 6, 8, 10,15,14,20])==False