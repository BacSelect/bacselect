import numpy as np
import pytest

from bacselect.correlation import spearman_correlation_matrix


def test_perfect_positive_and_negative_correlations() -> None:
    values = np.asarray(
        [
            [1.0, 10.0, 4.0],
            [2.0, 20.0, 3.0],
            [3.0, 30.0, 2.0],
            [4.0, 40.0, 1.0],
        ]
    )

    observed = spearman_correlation_matrix(values)

    expected = np.asarray(
        [
            [1.0, 1.0, -1.0],
            [1.0, 1.0, -1.0],
            [-1.0, -1.0, 1.0],
        ]
    )

    assert np.allclose(
        observed,
        expected,
        rtol=0.0,
        atol=1e-15,
    )


def test_tied_values_use_standard_spearman_ranks() -> None:
    values = np.asarray(
        [
            [1.0, 10.0, 30.0],
            [1.0, 10.0, 30.0],
            [2.0, 20.0, 20.0],
            [3.0, 30.0, 10.0],
            [3.0, 30.0, 10.0],
        ]
    )

    observed = spearman_correlation_matrix(values)

    assert observed[0, 1] == pytest.approx(1.0)
    assert observed[0, 2] == pytest.approx(-1.0)
    assert observed[1, 2] == pytest.approx(-1.0)


def test_two_columns_are_returned_as_two_by_two_matrix() -> None:
    values = np.asarray(
        [
            [1.0, 4.0],
            [2.0, 3.0],
            [3.0, 2.0],
            [4.0, 1.0],
        ]
    )

    observed = spearman_correlation_matrix(values)

    assert observed.shape == (2, 2)
    assert np.allclose(
        observed,
        np.asarray(
            [
                [1.0, -1.0],
                [-1.0, 1.0],
            ]
        ),
        rtol=0.0,
        atol=1e-15,
    )


def test_rejects_non_matrix_input() -> None:
    with pytest.raises(
        ValueError,
        match="two-dimensional",
    ):
        spearman_correlation_matrix(
            np.asarray([1.0, 2.0, 3.0])
        )


def test_rejects_too_few_rows() -> None:
    with pytest.raises(
        ValueError,
        match="at least two rows",
    ):
        spearman_correlation_matrix(
            np.asarray([[1.0, 2.0]])
        )


def test_rejects_too_few_columns() -> None:
    with pytest.raises(
        ValueError,
        match="at least two columns",
    ):
        spearman_correlation_matrix(
            np.asarray(
                [
                    [1.0],
                    [2.0],
                ]
            )
        )


def test_rejects_nonfinite_values() -> None:
    with pytest.raises(
        ValueError,
        match="finite",
    ):
        spearman_correlation_matrix(
            np.asarray(
                [
                    [1.0, 2.0],
                    [np.nan, 3.0],
                ]
            )
        )


def test_rejects_constant_column() -> None:
    with pytest.raises(
        ValueError,
        match="constant",
    ):
        spearman_correlation_matrix(
            np.asarray(
                [
                    [1.0, 5.0, 2.0],
                    [2.0, 5.0, 3.0],
                    [3.0, 5.0, 4.0],
                ]
            )
        )


def test_matrix_is_exactly_symmetric_by_construction() -> None:
    values = np.asarray(
        [
            [1.0, 8.0, 2.0, 4.0],
            [2.0, 7.0, 2.0, 1.0],
            [3.0, 6.0, 3.0, 5.0],
            [4.0, 5.0, 1.0, 3.0],
            [5.0, 4.0, 4.0, 2.0],
            [6.0, 3.0, 3.0, 6.0],
        ]
    )

    observed = spearman_correlation_matrix(values)

    assert np.array_equal(
        observed,
        observed.T,
    )

    assert np.array_equal(
        np.diag(observed),
        np.ones(values.shape[1]),
    )


def test_matrix_matches_individual_pairwise_spearman_calls() -> None:
    from scipy.stats import spearmanr

    values = np.asarray(
        [
            [1.0, 5.0, 2.0],
            [2.0, 5.0, 3.0],
            [3.0, 4.0, 1.0],
            [4.0, 2.0, 4.0],
            [5.0, 1.0, 4.0],
        ]
    )

    observed = spearman_correlation_matrix(values)

    for left in range(values.shape[1]):
        for right in range(left + 1, values.shape[1]):
            expected = float(
                spearmanr(
                    values[:, left],
                    values[:, right],
                    nan_policy="raise",
                ).statistic
            )

            assert observed[left, right] == expected
            assert observed[right, left] == expected
