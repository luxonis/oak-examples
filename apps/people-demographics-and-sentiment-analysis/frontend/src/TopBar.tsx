import { Flex, Separator } from '@luxonis/common-fe-components';

export const TopBar = () => {
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
        <Separator orientation="vertical" style={{ display: 'none' }} />
      </Flex>
    </Flex>
  );
};
