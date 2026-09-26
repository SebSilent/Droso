def split(str):
    split = 0
    for i in range(len(str)):
        if str[i] >= 'A' and str[i] <= 'Z':
            split += 1
        return split


assert split('python') == ['p','y','t','h','o','n']
assert split('Name') == ['N','a','m','e']
assert split('program') == ['p','r','o','g','r','a','m']