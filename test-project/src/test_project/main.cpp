// Copyright Steinwurf ApS 2015.
// All Rights Reserved
//
// Distributed under the "BSD License". See the accompanying LICENSE.rst file.

#include "some.hpp"

#include <iostream>

int main()
{
    test_project::some s;
    if (s.some_method())
    {
        std::cout << "Hello World!" << std::endl;
    }
    return 0;
}
