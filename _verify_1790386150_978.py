def armstrong_number(n):
    n = str(n)
    if len(n) <= 2:
        return False
    for i in range(2, len(n)):
        if n[i - 2] != n[i]:
            return False
    return True


assert armstrong_number(153)==True
assert armstrong_number(259)==False
assert armstrong_number(4458)==False