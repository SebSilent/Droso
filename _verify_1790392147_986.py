def armstrong_number(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert armstrong_number(153)==True
assert armstrong_number(259)==False
assert armstrong_number(4458)==False