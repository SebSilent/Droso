def reverse_words(stringlist):
    result = [x[::-1] for x in stringlist]
    return result


assert reverse_words("python program")==("program python")
assert reverse_words("java language")==("language java")
assert reverse_words("indian man")==("man indian")