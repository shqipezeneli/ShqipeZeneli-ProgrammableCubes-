"""Kontrolle eksplicite: nuk priten vlera dhjetore dhe nuk përdoret assert."""
from numbers import Integral


def validate_chromosome(values, num_cubes=148, max_commands=6000):
    data = list(values)
    if not data or any(isinstance(v, bool) or not isinstance(v, Integral) for v in data):
        raise ValueError('Kromozomi duhet të përmbajë vetëm numra të plotë.')
    if len(data) % 2 != 1 or data[-1] != -1 or -1 in data[:-1]:
        raise ValueError('Priten çifte (kub, komandë) dhe vetëm një -1 në fund.')
    if (len(data)-1)//2 > max_commands:
        raise ValueError('Tejkalohet numri maksimal i komandave.')
    if any(not 0 <= v < num_cubes for v in data[:-1:2]):
        raise ValueError('ID kubi jashtë kufijve.')
    if any(not 0 <= v < 6 for v in data[1:-1:2]):
        raise ValueError('ID komande jashtë kufijve.')
    return [int(v) for v in data]


def connected_unique(positions):
    occupied = {tuple(map(int, p)) for p in positions}
    if len(occupied) != len(positions) or not occupied:
        return False
    seen = {next(iter(occupied))}
    todo = list(seen)
    while todo:
        point = todo.pop()
        for axis in range(3):
            for direction in (-1, 1):
                neighbour = list(point)
                neighbour[axis] += direction
                neighbour = tuple(neighbour)
                if neighbour in occupied and neighbour not in seen:
                    seen.add(neighbour)
                    todo.append(neighbour)
    return len(seen) == len(occupied)
