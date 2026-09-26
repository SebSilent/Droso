from itertools import combinations_with_replacement 
def combinations_colors(l, n):
    return list(combinations_with_replacement(l,n))



assert replace_blank("hello people",'@')==("hello@people")
assert replace_blank("python program language",'$')==("python$program$language")
assert replace_blank("blank space","-")==("blank-space")