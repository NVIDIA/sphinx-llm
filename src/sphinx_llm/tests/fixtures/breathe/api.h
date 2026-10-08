// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/** A widget with a documented member. */
struct Widget {
    /** Number of items in the widget. */
    int count;
};

/** Available processing modes. */
enum Mode {
    /** Process every item. */
    All,
    /** Process only the first item. */
    First
};

/** Add two item counts.
 *
 * The detailed description survives the Markdown build.
 * \param left First item count.
 * \param right Second item count.
 * \return Combined item count.
 * \see Widget
 * \code
 * add(2, 3);
 * \endcode
 */
int add(int left, int right);
