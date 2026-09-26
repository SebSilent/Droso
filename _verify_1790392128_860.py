def split(str1):
    str2 = ''
    for i in range(1, len(str1) + 1):
        if i % 2 == 0:
            str2 = str2 + str1[i - 1]
    return str2


assert split('python') == ['p','y','t','h','o','n']
assert split('Name') == ['N','a','m','e']
assert split('program') == ['p','r','o','g','r','a','m']