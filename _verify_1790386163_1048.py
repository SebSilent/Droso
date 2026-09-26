def reverse_words(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert reverse_words("python program")==("program python")
assert reverse_words("java language")==("language java")
assert reverse_words("indian man")==("man indian")