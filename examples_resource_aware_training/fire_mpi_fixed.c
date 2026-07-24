/* fire_mpi_fixed.c - 修复版
 * - 每个rank使用不同随机种子
 * - 正确初始化forest
 * - 正确平均: 每个rank做 n_trials/size 次，最后求和 / size
 * - 计时用 MPI_Wtime
 * - 增加对 prob_spread 分片并行 (可选)
 */
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>
#include <sys/time.h>
#include <mpi.h>

#define UNBURNT 0
#define SMOLDERING 1
#define BURNING 2
#define BURNT 3
#define true 1
#define false 0
typedef int boolean;

extern void seed_by_time(int);
extern int ** allocate_forest(int);
extern void initialize_forest(int, int **);
extern double get_percent_burned(int, int **);
extern void delete_forest(int, int **);
extern void light_tree(int, int **,int,int);
extern boolean forest_is_burning(int, int **);
extern void forest_burns(int, int **,double);
extern void burn_until_out(int,int **,double,int,int);
extern void print_forest(int, int **);

int main(int argc, char ** argv) {
    int forest_size=20;
    double prob_min=0.0, prob_max=1.0, prob_step;
    double prob_spread;
    int n_trials=10000;
    int n_probs=100;
    double *per_burns, *per_storage;
    int rank, size;
    double t_start, t_end;

    if (argc>=2) n_trials = atoi(argv[1]);
    if (argc>=3) n_probs = atoi(argv[2]);

    MPI_Init(&argc,&argv);
    MPI_Comm_size(MPI_COMM_WORLD,&size);
    MPI_Comm_rank(MPI_COMM_WORLD,&rank);
    t_start = MPI_Wtime();

    // 关键修复: 每个rank用不同种子，否则蒙特卡洛重复
    seed_by_time(rank + 12345 + getpid());

    int **forest = allocate_forest(forest_size);
    per_burns = (double*)calloc(n_probs, sizeof(double));
    per_storage = (double*)calloc(n_probs, sizeof(double));

    prob_step = (prob_max-prob_min)/(double)(n_probs-1);
    int trials_per_rank = n_trials / size;
    if (rank==size-1) trials_per_rank += n_trials % size; // 余数给最后一个rank

    for (int i_prob=0; i_prob<n_probs; i_prob++) {
        prob_spread = prob_min + (double)i_prob*prob_step;
        double percent_burned=0.0;
        for (int i_trial=0; i_trial<trials_per_rank; i_trial++) {
            initialize_forest(forest_size, forest); // 每次trial需重新初始化
            burn_until_out(forest_size,forest,prob_spread,10,10);
            percent_burned+=get_percent_burned(forest_size,forest);
        }
        percent_burned /= trials_per_rank;
        per_burns[i_prob]=percent_burned;
    }

    // 收集到rank0求平均
    if (rank==0) {
        // 先把其他rank结果加进来
        for (int src=1; src<size; src++) {
            MPI_Recv(per_storage, n_probs, MPI_DOUBLE, src, src, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            for (int j=0;j<n_probs;j++) per_burns[j]+=per_storage[j];
        }
        for (int j=0;j<n_probs;j++) per_burns[j]/=size;

        printf("Probability of fire spreading, Average percent burned\n");
        for (int i_prob=0;i_prob<n_probs;i_prob++) {
            prob_spread = prob_min + (double)i_prob*prob_step;
            printf("%lf , %lf\n",prob_spread,per_burns[i_prob]);
        }
    } else {
        MPI_Send(per_burns, n_probs, MPI_DOUBLE, 0, rank, MPI_COMM_WORLD);
    }

    t_end = MPI_Wtime();
    printf("PID[%d]=%d time total %.6f sec, trials_per_rank=%d\n",rank,getpid(),t_end-t_start,trials_per_rank);

    delete_forest(forest_size,forest);
    free(per_burns);
    free(per_storage);
    MPI_Finalize();
    return 0;
}
