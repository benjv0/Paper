#ifndef CPU_AFFINITY_H
#define CPU_AFFINITY_H

#define _GNU_SOURCE
#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#define MAX_DETECTED_CORES 128

/* Parse a string of CPU ranges like "4-11" or "4,5,6,7" into integer array */
static inline int parse_cpu_list(const char *str, int *cores_out, int max_cores) {
    int count = 0;
    const char *p = str;

    while (*p && count < max_cores) {
        while (*p && (isspace(*p) || *p == ',')) p++;
        if (!*p) break;

        char *endptr;
        long start = strtol(p, &endptr, 10);
        if (p == endptr) break;

        long end = start;
        if (*endptr == '-') {
            p = endptr + 1;
            end = strtol(p, &endptr, 10);
        }
        p = endptr;

        for (long c = start; c <= end && count < max_cores; c++) {
            cores_out[count++] = (int)c;
        }
    }
    return count;
}

/* Autodetect E-cores from Linux sysfs /sys/devices/cpu_atom/cpus */
static inline int detect_ecores(int *cores_out, int max_cores) {
    FILE *fp = fopen("/sys/devices/cpu_atom/cpus", "r");
    if (!fp) {
        /* Fallback for Alder Lake i7-1255U if sysfs path not found */
        int fallback[] = {4, 5, 6, 7, 8, 9, 10, 11};
        int n = sizeof(fallback) / sizeof(fallback[0]);
        if (n > max_cores) n = max_cores;
        for (int i = 0; i < n; i++) cores_out[i] = fallback[i];
        return n;
    }

    char buf[256];
    if (!fgets(buf, sizeof(buf), fp)) {
        fclose(fp);
        return 0;
    }
    fclose(fp);

    return parse_cpu_list(buf, cores_out, max_cores);
}

/* Pin the specified pthread to a CPU ID */
static inline int pin_thread_to_core(pthread_t thread, int cpu_id) {
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(cpu_id, &cpuset);
    return pthread_setaffinity_np(thread, sizeof(cpu_set_t), &cpuset);
}

#endif /* CPU_AFFINITY_H */
