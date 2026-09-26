def change_date_format(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert change_date_format("2026-01-02") == '02-01-2026'
assert change_date_format("2020-11-13") == '13-11-2020'
assert change_date_format("2021-04-26") == '26-04-2021'