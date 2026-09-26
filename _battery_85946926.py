def is_palindrome(s):
    t = ''.join(c.lower() for c in s if not c.isspace())
    return t == t[::-1]

assert is_palindrome('Never odd or even')
assert not is_palindrome('droso')
