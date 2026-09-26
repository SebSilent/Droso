def armstrong_number(monthnum3):
    return monthnum3 == 4 or monthnum3 == 6 or monthnum3 == 9 or (monthnum3 == 11)


assert armstrong_number(153)==True
assert armstrong_number(259)==False
assert armstrong_number(4458)==False