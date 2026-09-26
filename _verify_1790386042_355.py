def insert_element(list,element):
 list = [v for elt in list for v in (element, elt)]
 return list


assert replace_blank("hello people",'@')==("hello@people")
assert replace_blank("python program language",'$')==("python$program$language")
assert replace_blank("blank space","-")==("blank-space")