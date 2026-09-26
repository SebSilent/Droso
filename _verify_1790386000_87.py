def is_sublist(A, B):
    n = len(A)
    m = len(B)
    i = 0
    j = 0
    while i < n and j < m:
        if A[i] == B[j]:
            i += 1
            j += 1
            if j == m:
                return True
        else:
            i = i - j + 1
            j = 0
    return False


assert is_sublist([2,4,3,5,7],[3,7])==False
assert is_sublist([2,4,3,5,7],[4,3])==True
assert is_sublist([2,4,3,5,7],[1,6])==False