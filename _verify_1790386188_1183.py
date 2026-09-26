def sum_list(*a):
    out = []
    for x in a[0]:
        for y in a[1]:
            out.append((x, y))
    return out



assert sum_list([10,20,30],[15,25,35])==[25,45,65]
assert sum_list([1,2,3],[5,6,7])==[6,8,10]
assert sum_list([15,20,30],[15,45,75])==[30,65,105]