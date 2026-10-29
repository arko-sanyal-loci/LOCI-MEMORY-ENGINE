#ifndef LOCI_GATE_H
#define LOCI_GATE_H

#include <math.h>
#include <stdbool.h>

/**
 * Single-Header Pure-C Ethical Valence Gate for Edge Devices (iOS, Android, Linux).
 * Zero dependencies beyond libm (tanh, fabs). Fully executable offline.
 */

typedef struct {
    double v_exec;
    bool execution_permitted;
    bool needs_human_review;
} GateResult;

static inline GateResult evaluate_loci_gate(
    double intent,
    double consent,
    double app_vector,
    double target_vulnerability,
    double c_id
) {
    const double DEFAULT_POSITIVE_BIAS = 0.08;
    const double BASE_REVIEW_WIDTH = 0.15;

    double penalty = (intent < 0.0) ? (target_vulnerability * (-intent)) : 0.0;
    double raw = DEFAULT_POSITIVE_BIAS + (0.95 * intent) + (0.65 * consent) + (0.70 * app_vector) - (0.40 * penalty);
    double v_exec = tanh(raw);

    double review_band = BASE_REVIEW_WIDTH * (1.0 - 0.85 * c_id);
    bool in_review = fabs(v_exec) < review_band;

    GateResult res;
    res.v_exec = v_exec;
    res.needs_human_review = in_review;
    res.execution_permitted = (v_exec > 0.0) && !in_review;
    return res;
}

#endif /* LOCI_GATE_H */
