"""Independent raw-segment polynomial quotient oracle for small cohorts."""
from fractions import Fraction as F

def add(left, right):
    return tuple((left[i] if i < len(left) else F(0)) +
                 (right[i] if i < len(right) else F(0))
                 for i in range(max(len(left), len(right))))

def multiply(left, right):
    result = [F(0)] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            result[i + j] += a * b
    return tuple(result)

def product(polynomials):
    result = (F(1),)
    for polynomial in polynomials:
        result = multiply(result, polynomial)
    return result

def quotient(numerator, denominator):
    n, d = sum(numerator), sum(denominator)
    dn = sum(i * x for i, x in enumerate(numerator))
    dd = sum(i * x for i, x in enumerate(denominator))
    return n / d, (dn * d - n * dd) / (d * d)

def oracle(rows, times, causes=(1, 2)):
    subjects = sorted({row.subject for row in rows})

    def evaluate(subject, time, cause):
        factors = []
        for event_time in sorted({row.exit for row in rows
                                  if row.event and row.exit <= time}):
            y, d, dc = (F(0), F(0)), (F(0), F(0)), (F(0), F(0))
            for row in rows:
                contribution = (F(0), row.weight) if row.subject == subject else (row.weight, F(0))
                if row.enter < event_time <= row.exit:
                    y = add(y, contribution)
                if row.exit == event_time and row.event:
                    d = add(d, contribution)
                    if row.event == cause:
                        dc = add(dc, contribution)
            remaining = add(y, tuple(-x for x in d))
            factors.append((y, remaining, dc))
        denominator = product([y for y, _, _ in factors])
        if cause == 0:
            numerator = product([remaining for _, remaining, _ in factors])
        else:
            numerator = (F(0),)
            for i, (_, _, dc) in enumerate(factors):
                term = product([dc] + [factors[j][1] for j in range(i)] +
                               [factors[j][0] for j in range(i + 1, len(factors))])
                numerator = add(numerator, term)
        return quotient(numerator, denominator)

    coordinates = [(t, c) for t in times for c in causes]
    probabilities = tuple(evaluate(None, t, c)[0] for t, c in coordinates)
    survival = tuple(evaluate(None, t, 0)[0] for t in times)
    gradients = [[evaluate(subject, t, c)[1] for t, c in coordinates]
                 for subject in subjects]
    covariance = tuple(tuple(sum((g[i] * g[j] for g in gradients), F(0))
                             for j in range(len(coordinates)))
                       for i in range(len(coordinates)))
    return survival, probabilities, covariance
