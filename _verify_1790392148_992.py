def armstrong_number(*a):
    return [x * x for x in a[0]]



assert armstrong_number(153)==True
assert armstrong_number(259)==False
assert armstrong_number(4458)==False