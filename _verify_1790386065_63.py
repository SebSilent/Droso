def min_of_three(*a):
    m = a[0][0]
    for x in a[0]:
        if x < m:
            m = x
    return m



assert min_of_three(10,20,0)==0
assert min_of_three(19,15,18)==15
assert min_of_three(-10,-20,-30)==-30