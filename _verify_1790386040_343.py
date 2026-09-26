def replace_blank(*a):
    return a[0].replace(a[1], a[2])



assert replace_blank("hello people",'@')==("hello@people")
assert replace_blank("python program language",'$')==("python$program$language")
assert replace_blank("blank space","-")==("blank-space")