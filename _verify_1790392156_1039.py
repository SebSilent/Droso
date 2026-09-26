def reverse_words(*a):
    return [x for x in a[0] if x]



assert reverse_words("python program")==("program python")
assert reverse_words("java language")==("language java")
assert reverse_words("indian man")==("man indian")