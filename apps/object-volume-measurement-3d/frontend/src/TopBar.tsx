import React from 'react';
import {
  Button,
  DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSubTrigger, DropdownMenuTrigger,
  Flex, Icon, Label, Tooltip, Separator,
} from '@luxonis/common-fe-components';
import {
    useDaiConnection, sortStreamsDefault, HIDDEN_STREAMS,
} from '@luxonis/depthai-viewer-common';
import { useLocation } from 'react-router-dom';
import { FaUsersViewfinder as VisualizerIcon } from 'react-icons/fa6';
import { StreamTypes } from '@luxonis/depthai-viewer-common';

const TopicSwitcher = () => {
  const { topics } = useDaiConnection();
  return topics.length !== 0 && (
    <DropdownMenu>
      <Tooltip content="Streams">
        <DropdownMenuTrigger>
          <TopicSwitcherButton />
        </DropdownMenuTrigger>
      </Tooltip>
      <DropdownMenuContent>
        <TopicSwitcherItems />
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const TopicSwitcherItems = () => {
  const { topics, toggleTopic } = useDaiConnection();
  const location = useLocation();
  const urlParams = new URLSearchParams(location.search);

  const [topicsList, setTopicsList] = React.useState<Record<string, boolean> | null>(
    topics.map((t) => t.name).includes(StreamTypes.NeuralNetwork)
      ? { [StreamTypes.NeuralNetwork]: false }
      : null,
  );

  React.useEffect(() => {
    if (topics.length === 0) return;
    setTopicsList(
      topics.reduce<Record<string, boolean>>((acc, topic) => {
        if (urlParams.get('streams')?.includes(topic.name) && !topic.name.startsWith('_')) {
          acc[topic.name] = true;
        }
        return acc;
      }, {}),
    );
    if (topics.find((n) =>
      n.name === StreamTypes.PointCloud ||
      n.name === StreamTypes._PointCloudColor ||
      n.name === StreamTypes.PointCloudColor,
    )?.enabled) {
      setTopicsList((prev) => ({ ...prev, [StreamTypes.PointCloud]: true }));
    }
  }, [topics, urlParams.get('streams')]);

  const checkTopic = React.useCallback((name: string, checked: boolean) => {
    setTopicsList((prev) => ({ ...prev, [name]: checked }));
  }, []);

  const sortedTopics = React.useMemo(
    () => sortStreamsDefault(
      topics.filter(
        (t) => !HIDDEN_STREAMS.includes(t.name as (typeof HIDDEN_STREAMS)[number]) && !t.name.startsWith('_'),
      ),
    ),
    [topics],
  );

  return sortedTopics.length !== 0 && topicsList ? (
    sortedTopics.map((topic, i) => (
      <DropdownMenuCheckboxItem
        key={i}
        onClick={() => toggleTopic(topic.name)}
        checked={topicsList[topic.name]}
        onCheckedChange={(checked) => checkTopic(topic.name, checked)}
      >
        {topic.name}
      </DropdownMenuCheckboxItem>
    ))
  ) : (
    <DropdownMenuItem disabled>No streams available</DropdownMenuItem>
  );
};

const TopicSwitcherButton = ({ type = 'button' }: { type?: 'trigger' | 'button' }) =>
  type === 'button' ? (
    <Button icon={VisualizerIcon} variant="outline" colorVariant="white" />
  ) : (
    <DropdownMenuSubTrigger>
      <Flex gap="xs" align="center">
        <Icon icon={VisualizerIcon} />
        <Label text="Streams" color="black" />
      </Flex>
    </DropdownMenuSubTrigger>
  );

/* ----- Top bar with logo + streams icon + columns menu ----- */
export const TopBar = () => {
  const { topics } = useDaiConnection();
  const logo = 'logo.svg';
  return (
    <Flex
      align="center"
      justify="space-between"
      gap="xs"
      padding="xs"
      width="full"
      style={{ borderBottom: '1px solid #d3d3d3d9' }}
    >
      <img src={logo} alt="Luxonis" style={{ width: '120px' }} />
      <Flex height="full" gap="sm" align="center">
        {topics.length !== 0 && (
          <>
            <TopicSwitcher />
          </>
        )}
        <Separator orientation="vertical" style={{ display: 'none' }} />
      </Flex>
    </Flex>
  );
};