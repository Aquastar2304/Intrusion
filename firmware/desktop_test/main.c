/* Desktop reference harness for rf5_n30_d10_f25 (5-class).
 * Writes row,label_idx,desktop_pred for every sample row (row = CSV line number, header = 1).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../esp32_ids_demo/model_rf5_n30_d10_f25.h"

#define N_FEAT 25

int main(int argc, char **argv) {
    if (argc < 3) { printf("usage: %s sample_inputs.csv out.csv\n", argv[0]); return 1; }
    FILE *fp = fopen(argv[1], "r"), *fo = fopen(argv[2], "w");
    if (!fp || !fo) { printf("cannot open input or output\n"); return 1; }
    char line[8192];
    fgets(line, sizeof(line), fp);
    fprintf(fo, "row,label_idx,desktop_pred\n");
    int total = 0, correct = 0, row = 1;
    float x[N_FEAT];
    while (fgets(line, sizeof(line), fp)) {
        row++;
        char *tok = strtok(line, ",");
        for (int i = 0; i < N_FEAT; i++) { x[i] = tok ? atof(tok) : 0.0f; tok = strtok(NULL, ","); }
        int true_idx = tok ? atoi(tok) : -1;
        int pred = model_rf5_n30_d10_f25_predict(x, N_FEAT);
        fprintf(fo, "%d,%d,%d\n", row, true_idx, pred);
        total++; if (pred == true_idx) correct++;
    }
    fclose(fp); fclose(fo);
    printf("desktop C: %d rows, accuracy = %.4f\n", total, total ? (double)correct / total : 0.0);
    return 0;
}
