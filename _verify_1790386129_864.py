def split(*a):
    return [x for x in a[0] if x % 2 == 1]



assert split('python') == ['p','y','t','h','o','n']
assert split('Name') == ['N','a','m','e']
assert split('program') == ['p','r','o','g','r','a','m']