def replace_blank(a, b):
    temp = a
    a = b
    b = temp
    return (a, b)


assert replace_blank("hello people",'@')==("hello@people")
assert replace_blank("python program language",'$')==("python$program$language")
assert replace_blank("blank space","-")==("blank-space")