#include <divsufsort.h>

#include <algorithm>
#include <cctype>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>


struct Replicon {
    std::string name;
    std::string sequence;
    bool circular = false;

    std::size_t forward_offset = 0;
    std::size_t reverse_offset = 0;
};


struct KmerResult {
    std::size_t k = 0;
    std::uint64_t valid_start_count = 0;
    std::uint64_t non_unique_start_count = 0;
    double non_unique_fraction = 0.0;
    std::uint64_t maximum_multiplicity = 0;
    std::uint64_t inter_replicon_shared_start_count = 0;
    double inter_replicon_shared_fraction = 0.0;
};


[[noreturn]]
void fail(const std::string &message) {
    throw std::runtime_error(message);
}


std::string reverse_complement(
    const std::string &sequence
) {
    std::string result;
    result.resize(sequence.size());

    for (
        std::size_t i = 0;
        i < sequence.size();
        ++i
    ) {
        const char base = sequence[
            sequence.size() - 1 - i
        ];

        switch (base) {
            case 'A':
                result[i] = 'T';
                break;
            case 'C':
                result[i] = 'G';
                break;
            case 'G':
                result[i] = 'C';
                break;
            case 'T':
                result[i] = 'A';
                break;
            default:
                fail(
                    "sequence contains non-ACGT symbol"
                );
        }
    }

    return result;
}


std::vector<std::string> split_tabs(
    const std::string &line
) {
    std::vector<std::string> fields;

    std::size_t start = 0;

    while (true) {
        const std::size_t tab = line.find(
            '\t',
            start
        );

        if (tab == std::string::npos) {
            fields.push_back(
                line.substr(start)
            );
            break;
        }

        fields.push_back(
            line.substr(
                start,
                tab - start
            )
        );

        start = tab + 1;
    }

    return fields;
}


std::vector<Replicon> read_replicons(
    const std::string &path
) {
    std::ifstream handle(path);

    if (!handle) {
        fail(
            "cannot open input: " + path
        );
    }

    std::string line;

    if (!std::getline(handle, line)) {
        fail("input is empty");
    }

    if (
        line
        != "name\ttopology\tsequence"
    ) {
        fail(
            "input header must be exactly: "
            "name<TAB>topology<TAB>sequence"
        );
    }

    std::vector<Replicon> replicons;
    std::unordered_set<std::string> names;

    std::size_t line_number = 1;

    while (std::getline(handle, line)) {
        ++line_number;

        if (line.empty()) {
            fail(
                "blank input line at line "
                + std::to_string(line_number)
            );
        }

        const auto fields = split_tabs(
            line
        );

        if (fields.size() != 3) {
            fail(
                "expected three tab-separated fields "
                "at line "
                + std::to_string(line_number)
            );
        }

        Replicon replicon;
        replicon.name = fields[0];

        if (replicon.name.empty()) {
            fail(
                "empty replicon name at line "
                + std::to_string(line_number)
            );
        }

        if (!names.insert(
            replicon.name
        ).second) {
            fail(
                "duplicate replicon name: "
                + replicon.name
            );
        }

        if (fields[1] == "circular") {
            replicon.circular = true;
        } else if (
            fields[1] == "linear"
        ) {
            replicon.circular = false;
        } else {
            fail(
                "unsupported topology at line "
                + std::to_string(line_number)
                + ": "
                + fields[1]
            );
        }

        replicon.sequence = fields[2];

        if (replicon.sequence.empty()) {
            fail(
                "empty sequence at line "
                + std::to_string(line_number)
            );
        }

        for (char &base : replicon.sequence) {
            base = static_cast<char>(
                std::toupper(
                    static_cast<unsigned char>(
                        base
                    )
                )
            );

            if (
                base != 'A'
                && base != 'C'
                && base != 'G'
                && base != 'T'
            ) {
                fail(
                    "sequence contains non-ACGT symbol "
                    "at line "
                    + std::to_string(line_number)
                );
            }
        }

        replicons.push_back(
            std::move(replicon)
        );
    }

    if (replicons.empty()) {
        fail(
            "input contains no replicons"
        );
    }

    return replicons;
}


void append_oriented_sequence(
    std::string &text,
    const std::string &sequence,
    bool circular,
    std::size_t maximum_k,
    std::size_t &offset
) {
    offset = text.size();

    text += sequence;

    if (
        circular
        && sequence.size() > 1
        && maximum_k > 1
    ) {
        const std::size_t extension_length = std::min(
            maximum_k - 1,
            sequence.size() - 1
        );

        text.append(
            sequence,
            0,
            extension_length
        );
    }

    // A separator outside A/C/G/T prevents matches
    // from silently crossing representation boundaries.
    text.push_back('#');
}


std::string build_generalized_text(
    std::vector<Replicon> &replicons,
    std::size_t maximum_k
) {
    std::string text;

    std::size_t reserve_size = 0;

    for (
        const auto &replicon : replicons
    ) {
        reserve_size += (
            2 * replicon.sequence.size()
            + 2 * maximum_k
            + 2
        );
    }

    text.reserve(
        reserve_size
    );

    for (auto &replicon : replicons) {
        append_oriented_sequence(
            text,
            replicon.sequence,
            replicon.circular,
            maximum_k,
            replicon.forward_offset
        );

        const std::string rc = reverse_complement(
            replicon.sequence
        );

        append_oriented_sequence(
            text,
            rc,
            replicon.circular,
            maximum_k,
            replicon.reverse_offset
        );
    }

    return text;
}


std::vector<saidx_t> build_suffix_array(
    const std::string &text
) {
    if (
        text.size()
        > static_cast<std::size_t>(
            std::numeric_limits<saidx_t>::max()
        )
    ) {
        fail(
            "generalized text exceeds libdivsufsort "
            "32-bit index capacity"
        );
    }

    std::vector<saidx_t> suffix_array(
        text.size()
    );

    const int rc = divsufsort(
        reinterpret_cast<const sauchar_t *>(
            text.data()
        ),
        suffix_array.data(),
        static_cast<saidx_t>(
            text.size()
        )
    );

    if (rc != 0) {
        fail(
            "divsufsort failed with code "
            + std::to_string(rc)
        );
    }

    return suffix_array;
}


std::vector<saidx_t> build_lcp_array(
    const std::string &text,
    const std::vector<saidx_t> &suffix_array
) {
    const std::size_t n = text.size();

    std::vector<saidx_t> rank(
        n
    );

    for (
        std::size_t r = 0;
        r < n;
        ++r
    ) {
        rank[
            static_cast<std::size_t>(
                suffix_array[r]
            )
        ] = static_cast<saidx_t>(
            r
        );
    }

    std::vector<saidx_t> lcp(
        n,
        0
    );

    std::size_t h = 0;

    for (
        std::size_t i = 0;
        i < n;
        ++i
    ) {
        const std::size_t r = static_cast<std::size_t>(
            rank[i]
        );

        if (r == 0) {
            continue;
        }

        const std::size_t j = static_cast<std::size_t>(
            suffix_array[r - 1]
        );

        while (
            i + h < n
            && j + h < n
            && text[i + h] == text[j + h]
        ) {
            ++h;
        }

        lcp[r] = static_cast<saidx_t>(
            h
        );

        if (h > 0) {
            --h;
        }
    }

    return lcp;
}


std::pair<
    std::vector<saidx_t>,
    std::size_t
>
build_kmer_classes(
    const std::vector<saidx_t> &suffix_array,
    const std::vector<saidx_t> &lcp,
    std::size_t k
) {
    const std::size_t n = suffix_array.size();

    std::vector<saidx_t> class_by_position(
        n
    );

    saidx_t class_id = 0;

    for (
        std::size_t r = 0;
        r < n;
        ++r
    ) {
        if (
            r > 0
            && static_cast<std::size_t>(
                lcp[r]
            ) < k
        ) {
            ++class_id;
        }

        class_by_position[
            static_cast<std::size_t>(
                suffix_array[r]
            )
        ] = class_id;
    }

    return {
        std::move(class_by_position),
        static_cast<std::size_t>(
            class_id
        ) + 1
    };
}


std::size_t reverse_start(
    std::size_t sequence_length,
    std::size_t source_start,
    std::size_t k,
    bool circular
) {
    if (!circular) {
        return (
            sequence_length
            - source_start
            - k
        );
    }

    const std::size_t endpoint = (
        source_start
        + k
    ) % sequence_length;

    return (
        sequence_length
        - endpoint
    ) % sequence_length;
}


KmerResult calculate_kmer_features(
    const std::vector<Replicon> &replicons,
    const std::vector<saidx_t> &suffix_array,
    const std::vector<saidx_t> &lcp,
    std::size_t k
) {
    const auto class_result = build_kmer_classes(
        suffix_array,
        lcp,
        k
    );

    const auto &class_by_position = (
        class_result.first
    );

    const std::size_t class_count = (
        class_result.second
    );

    std::vector<std::uint64_t> multiplicity(
        class_count,
        0
    );

    std::vector<std::int64_t> first_replicon(
        class_count,
        -1
    );

    std::vector<unsigned char> shared_between_replicons(
        class_count,
        0
    );

    KmerResult result;
    result.k = k;

    for (
        std::size_t replicon_index = 0;
        replicon_index < replicons.size();
        ++replicon_index
    ) {
        const auto &replicon = replicons[
            replicon_index
        ];

        const std::size_t n = (
            replicon.sequence.size()
        );

        if (n < k) {
            continue;
        }

        const std::size_t start_count = (
            replicon.circular
            ? n
            : n - k + 1
        );

        for (
            std::size_t source_start = 0;
            source_start < start_count;
            ++source_start
        ) {
            const std::size_t forward_position = (
                replicon.forward_offset
                + source_start
            );

            const std::size_t rc_start = reverse_start(
                n,
                source_start,
                k,
                replicon.circular
            );

            const std::size_t reverse_position = (
                replicon.reverse_offset
                + rc_start
            );

            const saidx_t forward_class = (
                class_by_position[
                    forward_position
                ]
            );

            const saidx_t reverse_class = (
                class_by_position[
                    reverse_position
                ]
            );

            // Class identifiers follow suffix-array lexical order.
            // Selecting the smaller class is therefore equivalent
            // to choosing min(kmer, reverse_complement(kmer)).
            const std::size_t canonical_class = (
                static_cast<std::size_t>(
                    std::min(
                        forward_class,
                        reverse_class
                    )
                )
            );

            ++multiplicity[
                canonical_class
            ];

            ++result.valid_start_count;

            if (
                first_replicon[
                    canonical_class
                ] < 0
            ) {
                first_replicon[
                    canonical_class
                ] = static_cast<std::int64_t>(
                    replicon_index
                );
            } else if (
                first_replicon[
                    canonical_class
                ]
                != static_cast<std::int64_t>(
                    replicon_index
                )
            ) {
                shared_between_replicons[
                    canonical_class
                ] = 1;
            }
        }
    }

    for (
        std::size_t class_id = 0;
        class_id < class_count;
        ++class_id
    ) {
        const std::uint64_t count = (
            multiplicity[
                class_id
            ]
        );

        if (count == 0) {
            continue;
        }

        result.maximum_multiplicity = std::max(
            result.maximum_multiplicity,
            count
        );

        if (count > 1) {
            result.non_unique_start_count += (
                count
            );
        }

        if (
            shared_between_replicons[
                class_id
            ] != 0
        ) {
            result.inter_replicon_shared_start_count += (
                count
            );
        }
    }

    if (
        result.valid_start_count > 0
    ) {
        result.non_unique_fraction = (
            static_cast<double>(
                result.non_unique_start_count
            )
            / static_cast<double>(
                result.valid_start_count
            )
        );

        result.inter_replicon_shared_fraction = (
            static_cast<double>(
                result.inter_replicon_shared_start_count
            )
            / static_cast<double>(
                result.valid_start_count
            )
        );
    }

    return result;
}


bool repeat_exists_at_length(
    const std::vector<Replicon> &replicons,
    const std::vector<saidx_t> &suffix_array,
    const std::vector<saidx_t> &lcp,
    std::size_t length
) {
    if (length == 0) {
        return true;
    }

    bool any_valid_start = false;

    for (const auto &replicon : replicons) {
        if (replicon.sequence.size() >= length) {
            any_valid_start = true;
            break;
        }
    }

    if (!any_valid_start) {
        return false;
    }

    const KmerResult result = calculate_kmer_features(
        replicons,
        suffix_array,
        lcp,
        length
    );

    return result.maximum_multiplicity > 1;
}


std::size_t longest_exact_repeat_length(
    const std::vector<Replicon> &replicons,
    const std::vector<saidx_t> &suffix_array,
    const std::vector<saidx_t> &lcp
) {
    std::size_t maximum_possible = 0;

    for (const auto &replicon : replicons) {
        maximum_possible = std::max(
            maximum_possible,
            replicon.sequence.size()
        );
    }

    // Invariant:
    //   low is a length for which a repeat exists, with length zero
    //   serving as the trivial lower bound.
    //   high is a length for which no valid repeated occurrence can
    //   exist. No occurrence may exceed its source replicon length.
    std::size_t low = 0;
    std::size_t high = maximum_possible + 1;

    while (low + 1 < high) {
        const std::size_t middle = (
            low
            + (high - low) / 2
        );

        if (
            repeat_exists_at_length(
                replicons,
                suffix_array,
                lcp,
                middle
            )
        ) {
            low = middle;
        } else {
            high = middle;
        }
    }

    return low;
}


int main(
    int argc,
    char **argv
) {
    try {
        std::string input_path;
        std::vector<std::size_t> k_values;
        bool calculate_longest_repeat = false;

        for (
            int i = 1;
            i < argc;
            ++i
        ) {
            const std::string arg = argv[i];

            if (arg == "--input") {
                if (i + 1 >= argc) {
                    fail(
                        "--input requires a path"
                    );
                }

                input_path = argv[
                    ++i
                ];
            } else if (arg == "--k") {
                if (i + 1 >= argc) {
                    fail(
                        "--k requires an integer"
                    );
                }

                const std::string raw = argv[
                    ++i
                ];

                std::size_t consumed = 0;

                const unsigned long parsed = std::stoul(
                    raw,
                    &consumed
                );

                if (
                    consumed != raw.size()
                    || parsed == 0
                ) {
                    fail(
                        "invalid k: " + raw
                    );
                }

                k_values.push_back(
                    static_cast<std::size_t>(
                        parsed
                    )
                );
            } else if (
                arg == "--longest-repeat"
            ) {
                calculate_longest_repeat = true;
            } else {
                fail(
                    "unknown argument: " + arg
                );
            }
        }

        if (input_path.empty()) {
            fail("--input is required");
        }

        if (k_values.empty()) {
            fail(
                "at least one --k is required"
            );
        }

        std::sort(
            k_values.begin(),
            k_values.end()
        );

        k_values.erase(
            std::unique(
                k_values.begin(),
                k_values.end()
            ),
            k_values.end()
        );

        auto replicons = read_replicons(
            input_path
        );

        std::size_t maximum_k = (
            k_values.back()
        );

        if (calculate_longest_repeat) {
            for (const auto &replicon : replicons) {
                maximum_k = std::max(
                    maximum_k,
                    replicon.sequence.size()
                );
            }
        }

        const std::string text = build_generalized_text(
            replicons,
            maximum_k
        );

        const auto suffix_array = build_suffix_array(
            text
        );

        const auto lcp = build_lcp_array(
            text,
            suffix_array
        );

        std::size_t longest_repeat = 0;

        if (calculate_longest_repeat) {
            longest_repeat = longest_exact_repeat_length(
                replicons,
                suffix_array,
                lcp
            );
        }

        std::cout
            << "k"
            << '\t'
            << "valid_start_count"
            << '\t'
            << "non_unique_start_count"
            << '\t'
            << "non_unique_fraction"
            << '\t'
            << "maximum_multiplicity"
            << '\t'
            << "inter_replicon_shared_start_count"
            << '\t'
            << "inter_replicon_shared_fraction";

        if (calculate_longest_repeat) {
            std::cout
                << '\t'
                << "longest_exact_repeat_length";
        }

        std::cout
            << '\n';

        std::cout
            << std::setprecision(17);

        for (
            const std::size_t k : k_values
        ) {
            const KmerResult result = (
                calculate_kmer_features(
                    replicons,
                    suffix_array,
                    lcp,
                    k
                )
            );

            std::cout
                << result.k
                << '\t'
                << result.valid_start_count
                << '\t'
                << result.non_unique_start_count
                << '\t'
                << result.non_unique_fraction
                << '\t'
                << result.maximum_multiplicity
                << '\t'
                << result.inter_replicon_shared_start_count
                << '\t'
                << result.inter_replicon_shared_fraction;

            if (calculate_longest_repeat) {
                std::cout
                    << '\t'
                    << longest_repeat;
            }

            std::cout
                << '\n';
        }

        return 0;

    } catch (
        const std::exception &exc
    ) {
        std::cerr
            << "ERROR | "
            << exc.what()
            << '\n';

        return 1;
    }
}
