import heapq
def larg_nnum(list1,n):
 largest=heapq.nlargest(n,list1)
 return largest


assert replace_blank("hello people",'@')==("hello@people")
assert replace_blank("python program language",'$')==("python$program$language")
assert replace_blank("blank space","-")==("blank-space")