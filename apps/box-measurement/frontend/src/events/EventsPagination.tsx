import { Button, Flex, NormalText } from "@luxonis/common-fe-components";

type EventsPaginationProps = {
    page: number;
    totalPages: number;
    isDisabled?: boolean;
    onPageChange: (page: number) => void;
};

function getVisiblePageItems(page: number, totalPages: number) {
    const pages = new Set([
        1,
        totalPages,
        page - 1,
        page,
        page + 1,
    ]);

    const visiblePages = [...pages]
        .filter((item) => item >= 1 && item <= totalPages)
        .sort((left, right) => left - right);

    const items: Array<number | string> = [];

    for (const visiblePage of visiblePages) {
        const previousItem = items[items.length - 1];

        if (
            typeof previousItem === "number" &&
            visiblePage - previousItem > 1
        ) {
            items.push(`ellipsis-${previousItem}-${visiblePage}`);
        }

        items.push(visiblePage);
    }

    return items;
}

export function EventsPagination({
    page,
    totalPages,
    isDisabled = false,
    onPageChange,
}: EventsPaginationProps) {
    const pageItems = getVisiblePageItems(page, totalPages);

    return (
        <Flex direction="column" width="full" alignItems="center" gap="sm">
            <NormalText text={`Page ${page} of ${totalPages}`} />

            <Flex
                width="full"
                alignItems="center"
                justifyContent="center"
                gap="xs"
                flexWrap="wrap"
            >
                <Button
                    type="button"
                    variant="ghost"
                    label="Previous"
                    disabled={page <= 1 || isDisabled}
                    onClick={() => {
                        onPageChange(page - 1);
                    }}
                />

                {pageItems.map((item) =>
                    typeof item === "number" ? (
                        <Button
                            key={item}
                            type="button"
                            variant={item === page ? "filled" : "ghost"}
                            label={String(item)}
                            disabled={isDisabled}
                            onClick={() => {
                                onPageChange(item);
                            }}
                        />
                    ) : (
                        <NormalText key={item} text="..." />
                    ),
                )}

                <Button
                    type="button"
                    variant="ghost"
                    label="Next"
                    disabled={page >= totalPages || isDisabled}
                    onClick={() => {
                        onPageChange(page + 1);
                    }}
                />
            </Flex>
        </Flex>
    );
}
