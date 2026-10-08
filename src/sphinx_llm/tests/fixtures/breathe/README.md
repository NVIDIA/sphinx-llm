# Breathe regression fixture

`xml/index.xml`, `xml/api_8h.xml`, and `xml/structWidget.xml` were generated
from `api.h` by Doxygen 1.9.8. They exercise actual Breathe parsing without
requiring Doxygen in every unit-test environment.

To regenerate, run `doxygen Doxyfile` in this directory. Keep only the three
XML files above; Breathe does not need the generated schemas or configuration
dump. The function's explicit `\brief` creates a nonempty `briefdescription`,
separate from its detailed description; the regression test verifies both XML
elements and their rendered text. The header also covers parameter and return
descriptions, a code example, a cross-page see-also reference, a struct member,
and enum values.
