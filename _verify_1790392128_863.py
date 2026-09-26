def split(str1):
    total = 0
    for i in str1:
        total = total + 1
    return total


assert split('python') == ['p','y','t','h','o','n']
assert split('Name') == ['N','a','m','e']
assert split('program') == ['p','r','o','g','r','a','m']