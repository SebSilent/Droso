def split(str1,ch,newch):
 str2 = str1.replace(ch, newch)
 return str2


assert split('python') == ['p','y','t','h','o','n']
assert split('Name') == ['N','a','m','e']
assert split('program') == ['p','r','o','g','r','a','m']