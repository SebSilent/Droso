def dict_depth(d):
    if isinstance(d, dict):
        return 1 + (max(map(dict_depth, d.values())) if d else 0)
    return 0


assert parabola_directrix(5,3,2)==-198
assert parabola_directrix(9,8,4)==-2336
assert parabola_directrix(2,4,6)==-130