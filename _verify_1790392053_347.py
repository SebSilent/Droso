def volume_cylinder(r,h):
  volume=3.1415*r*r*h
  return volume


assert replace_blank("hello people",'@')==("hello@people")
assert replace_blank("python program language",'$')==("python$program$language")
assert replace_blank("blank space","-")==("blank-space")