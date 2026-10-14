#include <ceres/ceres.h>
#include <ceres/local_parameterization.h>
#include <ceres/version.h>
#include <iostream>

int main() {
    static_assert(CERES_VERSION_MAJOR == 2 && CERES_VERSION_MINOR == 1);
    ceres::Problem problem;
    ceres::LocalParameterization* legacy_api = nullptr;
    std::cout << "Ceres " << CERES_VERSION_STRING << ", legacy API: "
              << (legacy_api == nullptr) << '\n';
    return 0;
}
