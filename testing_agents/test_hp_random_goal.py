import sys
import os
import ipdb
import pickle
import json
import random
import numpy as np
from pathlib import Path

from envs.unity_environment import UnityEnvironment
from agents import MCTS_agent
from arguments import get_args
from algos.arena_mp2 import ArenaMP
from utils import utils_goals


def random_goal(graph, seed=None):
    preds = [
    "on_plate_kitchentable",
    "on_waterglass_kitchentable",
    "on_wineglass_kitchentable",
    "on_cutleryfork_kitchentable",
    "inside_plate_dishwasher",
    "inside_waterglass_dishwasher",
    "inside_wineglass_dishwasher",
    "inside_cutleryfork_dishwasher",
    "inside_cupcake_fridge",
    "inside_juice_fridge",
    "inside_pancake_fridge",
    "inside_poundcake_fridge",
    "inside_wine_fridge",
    "inside_pudding_fridge",
    "inside_apple_fridge",
    "on_cupcake_kitchentable",
    "on_juice_kitchentable",
    "on_pancake_kitchentable",
    "on_poundcake_kitchentable",
    "on_wine_kitchentable",
    "on_pudding_kitchentable",
    "on_apple_kitchentable",
    "on_coffeepot_kitchentable",
    "on_cupcake_coffeetable",
    "on_juice_coffeetable",
    "on_wine_coffeetable",
    "on_pudding_coffeetable",
    "on_apple_coffeetable"]

    if seed is not None:
        random_object = random.Random(seed)
    else:
        random_object = random.Random()

    idnodes = {}
    for class_name in ['fridge', 'dishwasher', 'kitchentable', 'coffeetable']:
        idnodes[class_name] = [node['id'] for node in graph['nodes'] if node['class_name'] == class_name][0]

    preds_selected = random_object.choices(preds, k=6)
    dict_preds = {}
    for pred in preds_selected:

        spl = pred.split('_')
        id_target = idnodes[spl[-1]]
        target_name = '{}_{}_{}'.format(spl[0], spl[1], id_target)
        dict_preds[target_name] = random_object.choice([0,1,2])
    return dict_preds



if __name__ == '__main__':
    args = get_args()
    
    args.max_episode_length = 250
    args.num_per_apartment = 10
    args.mode = 'hp_randomgoal'
    args.dataset_path = './dataset/test_env_set_help.pik'
    args.executable_file = '../virtualhome/macos_exec.app'

    env_task_set = pickle.load(open(args.dataset_path, 'rb'))
    args.record_dir = '../test_results/multiBob_env_task_set_{}_{}'.format(args.num_per_apartment, args.mode)
    executable_args = {
                    'file_name': args.executable_file,
                    'x_display': 0,
                    'no_graphics': True
    }

    id_run = 0
    random.seed(id_run)
    episode_ids = list(range(len(env_task_set)))
    episode_ids = sorted(episode_ids)
    num_tries = 5
    S = [[] for _ in range(len(episode_ids))]
    L = [[] for _ in range(len(episode_ids))]
    
    test_results = {}

    def env_fn(env_id):
        return UnityEnvironment(num_agents=2,
                               max_episode_length=args.max_episode_length,
                               port_id=env_id,
                               env_task_set=env_task_set,
                               observation_types=[args.obs_type, args.obs_type],
                               use_editor=args.use_editor,
                               executable_args=executable_args,
                               base_port=args.base_port)

    args_common = dict(recursive=False,
                         max_episode_length=5,
                         num_simulation=100,
                         max_rollout_steps=5,
                         c_init=0.1,
                         c_base=1000000,
                         num_samples=1,
                         num_processes=1,
                         logging=True,
                         logging_graphs=True)

    args_agent1 = {'agent_id': 1, 'char_index': 0}
    args_agent2 = {'agent_id': 2, 'char_index': 1}
    args_agent1.update(args_common)
    args_agent2.update(args_common)
    args_agent2.update({'recursive': False})
    agents = [lambda x, y: MCTS_agent(**args_agent1), lambda x, y: MCTS_agent(**args_agent2)]
    arena = ArenaMP(args.max_episode_length, id_run, env_fn, agents)

    for iter_id in range(num_tries):
        
        steps_list, failed_tasks = [], []
        if not os.path.isfile(args.record_dir + '/results_{}.pik'.format(0)):
            test_results = {}
        else:
            test_results = pickle.load(open(args.record_dir + '/results_{}.pik'.format(0), 'rb'))

        current_tried = iter_id
        for episode_id in episode_ids:
            
            curr_log_file_name = args.record_dir + '/logs_agent_{}_{}_{}.pik'.format(
                env_task_set[episode_id]['task_id'],
                env_task_set[episode_id]['task_name'],
                iter_id)

            

            if os.path.isfile(curr_log_file_name):
                with open(curr_log_file_name, 'rb') as fd:
                    file_data = pickle.load(fd)
                S[episode_id][current_tried] = file_data['finished']
                L[episode_id][current_tried] = max(len(file_data['action'][0]), len(file_data['action'][1]))
                test_results[episode_id] = {'S': S[episode_id],
                                            'L': L[episode_id]}
                continue

            print('episode:', episode_id)

            for it_agent, agent in enumerate(arena.agents):
                agent.seed = it_agent + current_tried * 2

            is_finished = 0
            steps = 250
            try:
                curr_seed = current_tried + episode_id * num_tries
                
                arena.reset(episode_id)
                rand_goal = random_goal(arena.env.graph, curr_seed)
                original_goal = arena.env.task_goal[0]
                success, steps, saved_info = arena.run(pred_goal={0: original_goal, 1: rand_goal})
                print('-------------------------------------')
                print('success' if success else 'failure')
                print('steps:', steps)
                print('-------------------------------------')
                if not success:
                    failed_tasks.append(episode_id)
                else:
                    steps_list.append(steps)
                is_finished = 1 if success else 0
                Path(args.record_dir).mkdir(parents=True, exist_ok=True)
                log_file_name = args.record_dir + '/logs_agent_{}_{}_{}.pik'.format(saved_info['task_id'],
                                                                                    saved_info['task_name'],
                                                                                    current_tried)

                if len(saved_info['obs']) > 0:
                    pickle.dump(saved_info, open(log_file_name, 'wb'))
                else:
                    with open(log_file_name, 'w+') as f:
                        f.write(json.dumps(saved_info, indent=4))
            except:
                ipdb.set_trace()
                arena.reset_env()

            S[episode_id].append(is_finished)
            L[episode_id].append(steps)
            test_results[episode_id] = {'S': S[episode_id],
                                        'L': L[episode_id]}
        pickle.dump(test_results, open(args.record_dir + '/results_{}.pik'.format(0), 'wb'))
        print('average steps (finishing the tasks):', np.array(steps_list).mean() if len(steps_list) > 0 else None)
        print('failed_tasks:', failed_tasks)
        pickle.dump(test_results, open(args.record_dir + '/results_{}.pik'.format(0), 'wb'))
